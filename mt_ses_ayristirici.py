"""
============================================================
  Çağrı Merkezi — MT Ses Çıkarıcı (Sıfır Kayıp)
  ============================================================
  - pydub / FFmpeg KULLANMAZ → codec dönüşümü olmaz
  - Python dahili wave + struct modülleri ile ham byte işlemi
  - Orijinal sample rate, bit depth birebir korunur

  Kurulum: Ekstra kütüphane gerekmez.

  Kullanım:
    python mt_ses_ayristirici_final.py
    python mt_ses_ayristirici_final.py --input dosya.wav
    python mt_ses_ayristirici_final.py --input dosya.wav --output cikti.wav
============================================================
"""

import wave
import struct
import argparse
import sys
from pathlib import Path

# ── Varsayılan Yollar ─────────────────────────────────────────────
VARSAYILAN_GIRIS        = r"c:/Users/GLB90125308/Desktop/veri-bolme/02/1d1e8d1a-4933-4935-9f04-d46353ff64d1.wav"
VARSAYILAN_CIKIS_KLASOR = Path(r"c:/Users/GLB90125308/Desktop/veri-bolme/ayrilmis_veri")


def wav_bilgi_al(dosya: str) -> dict:
    """WAV dosyasının teknik özelliklerini ham (raw) okuyarak döner.
    Python wave modülü format 6 (A-Law) desteklemese de bu fonksiyon okur."""
    with open(dosya, "rb") as f:
        if f.read(4) != b'RIFF': raise ValueError("RIFF başlığı yok")
        f.read(4) # Dosya boyutu
        if f.read(4) != b'WAVE': raise ValueError("WAVE başlığı yok")
        
        bilgi = {"diger_chunklar": []}
        while True:
            header = f.read(8)
            if len(header) < 8: break
            chunk_id, chunk_size = struct.unpack("<4sI", header)
            chunk_data = f.read(chunk_size)
            if chunk_size % 2 == 1: f.read(1) # padding
            
            if chunk_id == b'fmt ':
                fmt, kanallar, sr, br, ba, bps = struct.unpack("<HHIIHH", chunk_data[:16])
                bilgi.update({
                    "format": fmt, "kanallar": kanallar, "sample_rate": sr, 
                    "byte_rate": br, "block_align": ba, "bits_per_sample": bps, 
                    "fmt_data": chunk_data
                })
            elif chunk_id == b'data':
                bilgi["data"] = chunk_data
                # Daha fazla okumaya gerek yok, veriyi alıp çıkıyoruz
            else:
                bilgi["diger_chunklar"].append((chunk_id, chunk_data))
                
        if "data" not in bilgi or "format" not in bilgi:
            raise ValueError("Bozuk WAV: fmt veya data chunk eksik")
            
        bilgi["sure_sn"] = len(bilgi["data"]) / bilgi.get("byte_rate", 1)
        return bilgi


def sol_kanali_cikart(giris: str, cikis: str) -> None:
    """
    Stereo WAV → sol kanal (MT) ayıklama (Tüm formatlar: PCM, A-Law, u-Law).
    Hiçbir matematiksel kodlama uygulanmaz, sadece baytlar ayrılır.
    """
    if not Path(giris).exists():
        print(f"❌ Dosya bulunamadı: {giris}")
        sys.exit(1)

    try:
        bilgi = wav_bilgi_al(giris)
    except Exception as e:
        print(f"❌ WAV okunamadı: {e}")
        sys.exit(1)

    print(f"\n📂 {Path(giris).name}")
    print(f"   Format      : {bilgi['format']} (6=ALaw, 7=uLaw, 1=PCM)")
    print(f"   Kanallar    : {bilgi['kanallar']}")
    print(f"   Sample rate : {bilgi['sample_rate']} Hz")
    print(f"   Süre        : {bilgi['sure_sn']:.1f} saniye")

    if bilgi["kanallar"] != 2:
        print(f"\n❌ Stereo dosya gerekli (mevcut: {bilgi['kanallar']} kanal)")
        sys.exit(1)

    # ── 1. Sol Kanalı Ayır (Ham Byte İşlemi) ─────────────────────────
    print("\n🔄 Ham veri okunuyor ve ayrıştırılıyor...")
    block_align = bilgi["block_align"]
    bytes_per_channel = block_align // 2
    raw_data = bilgi["data"]
    
    sol_kanal = bytearray()
    for i in range(0, len(raw_data), block_align):
        sol_kanal.extend(raw_data[i:i+bytes_per_channel])
        
    print(f"✂️  Sol kanal (MT) ayrıştırıldı")

    # ── 2. Yeni WAV Başlıklarını Oluştur ──────────────────────────────
    new_kanallar = 1
    new_block_align = bytes_per_channel
    new_byte_rate = bilgi["sample_rate"] * new_block_align
    
    # 16 baytlık temel ses formatını pack et, ekstra fmt datası varsa ekle
    yeni_fmt_temel = struct.pack("<HHIIHH", 
        bilgi["format"], new_kanallar, bilgi["sample_rate"], 
        new_byte_rate, new_block_align, bilgi["bits_per_sample"]
    )
    yeni_fmt_tam = yeni_fmt_temel + bilgi["fmt_data"][16:]
    
    new_fmt_chunk = b'fmt ' + struct.pack("<I", len(yeni_fmt_tam)) + yeni_fmt_tam
    new_data_chunk = b'data' + struct.pack("<I", len(sol_kanal)) + sol_kanal
    
    # Yeni dosyayı birleştir (sadece ses ve format tutulur)
    wav_icerik = b'WAVE' + new_fmt_chunk + new_data_chunk
    
    # ── 3. Çıktıyı Yaz ────────────────────────────────────────────────
    Path(cikis).parent.mkdir(parents=True, exist_ok=True)
    print(f"💾 Yazılıyor: {cikis}")
    try:
        with open(cikis, "wb") as yazici:
            yazici.write(b'RIFF' + struct.pack('<I', len(wav_icerik)) + wav_icerik)
    except Exception as e:
        print(f"❌ Yazma hatası: {e}")
        sys.exit(1)

    # ── 4. Özet ───────────────────────────────────────────────────
    boyut_kb = Path(cikis).stat().st_size / 1024
    print("\n" + "─" * 44)
    print("✅ Tamamlandı — sıfır kayıp (byte-perfect)!")
    print(f"   Çıktı       : {Path(cikis).name}")
    print(f"   Klasör      : {Path(cikis).parent}")
    print(f"   Format      : {bilgi['format']} ✓ (korundu)")
    print(f"   Sample rate : {bilgi['sample_rate']} Hz ✓ (korundu)")
    print(f"   Boyut       : {boyut_kb:.1f} KB")
    print("─" * 44 + "\n")


# ── Ana Akış ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Stereo çağrı kaydından MT sesini sıfır kalite kaybıyla ayıklar.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python mt_ses_ayristirici_final.py
  python mt_ses_ayristirici_final.py --input kayit.wav
  python mt_ses_ayristirici_final.py --input kayit.wav --output cikti.wav
        """
    )
    parser.add_argument(
        "--input", "-i",
        default=VARSAYILAN_GIRIS,
        help="Kaynak stereo WAV dosyası"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Çıktı WAV dosyası (belirtilmezse ayrilmis_veri klasörüne kaydedilir)"
    )
    args = parser.parse_args()

    # Çıktı yolu belirtilmemişse otomatik oluştur
    if not args.output:
        input_path  = Path(args.input)
        args.output = str(VARSAYILAN_CIKIS_KLASOR / f"{input_path.stem}_mt{input_path.suffix}")

    print("=" * 44)
    print("  MT Ses Çıkarıcı — Sıfır Kayıp")
    print("=" * 44)
    print(f"  Girdi  : {args.input}")
    print(f"  Çıktı  : {args.output}")

    sol_kanali_cikart(args.input, args.output)


if __name__ == "__main__":
    main()