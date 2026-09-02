# ==========================================================
# DAFTAR AFILIASI GRUP KONGLOMERASI — SUMBER: DATA MANUAL PENGGUNA
# + VERIFIKASI RISET WEB (2026-09-03)
# ==========================================================
# CATATAN PENTING: Data kepemilikan/afiliasi di bawah ini BUKAN dari
# sumber resmi IDX/OJK yang terverifikasi otomatis — ini kompilasi
# riset manual (dari pengguna aplikasi ini) yang sebagian barisnya
# dilengkapi lewat riset berita keuangan (Kontan, Bisnis.com, CNBC
# Indonesia, dll). Selalu cek ulang ke laporan keterbukaan informasi
# / prospektus resmi sebelum dipakai sebagai dasar keputusan
# investasi. Satu kode saham bisa muncul di lebih dari satu grup
# kalau memang dimiliki bersama (joint venture).
#
# Beberapa kode dari daftar awal SENGAJA TIDAK dimasukkan karena
# riset menemukan afiliasinya sudah tidak berlaku lagi:
#   - GZCO (Prajogo Pangestu keluar sejak Okt 2023, kini dikendalikan
#     Tjandra Mindharta Gozali — tidak terkait Barito Pacific)
#   - PADI (Hapsoro melepas seluruh sahamnya Maret 2026)
#   - LINK (masih dikendalikan Axiata; rencana divestasi ke
#     Sinarmas baru sebatas rumor, belum terealisasi)
#   - PYFA (dikendalikan Rejuve Global Investment/Lee Ee Ling,
#     tidak terkait Sinarmas — alamat kantor di gedung Sinarmas
#     hanya kebetulan sewa gedung)
# ==========================================================

KONGLOMERAT_LIST = {
    "Bakrie": [
        {"kode": "BNBR", "nama": "Bakrie & Brothers", "sektor": "Investasi & Industri", "status": "Pengendali", "catatan": ""},
        {"kode": "BUMI", "nama": "Bumi Resources", "sektor": "Batu Bara", "status": "Pengendali", "catatan": ""},
        {"kode": "BRMS", "nama": "Bumi Resources Minerals", "sektor": "Emas & Mineral", "status": "Pengendali", "catatan": ""},
        {"kode": "ENRG", "nama": "Energi Mega Persada", "sektor": "Minyak & Gas", "status": "Pengendali", "catatan": ""},
        {"kode": "ELTY", "nama": "Bakrieland Development", "sektor": "Properti", "status": "Pengendali", "catatan": ""},
        {"kode": "UNSP", "nama": "Bakrie Sumatera Plantations", "sektor": "Perkebunan", "status": "Pengendali", "catatan": ""},
        {"kode": "DEWA", "nama": "Darma Henwa", "sektor": "Kontraktor Tambang", "status": "Pengendali", "catatan": ""},
        {"kode": "VIVA", "nama": "Visi Media Asia", "sektor": "Media", "status": "Pengendali", "catatan": "Punya riwayat suspensi panjang - cek status terkini di BEI"},
        {"kode": "JGLE", "nama": "Graha Andrasentra Propertindo", "sektor": "Properti & Rekreasi (Jungleland)", "status": "Afiliasi", "catatan": "Anak usaha ELTY (38,76%); mayoritas Jungleland Asia sudah dilepas ke investor luar Sept 2022"},
        {"kode": "MDIA", "nama": "Intermedia Capital", "sektor": "Media & Konten (induk ANTV)", "status": "Afiliasi", "catatan": "VIVA menguasai 80,73%; masuk daftar HSC (pengawasan khusus) BEI Agustus 2026"},
        {"kode": "VKTR", "nama": "VKTR Teknologi Mobilitas", "sektor": "Manufaktur Kendaraan Listrik", "status": "Pengendali", "catatan": "BNBR + Bakrie Steel Industries ~39,86%; investor global (Glencore, dll) mulai masuk 2026"},
    ],
    "Salim": [
        {"kode": "INDF", "nama": "Indofood Sukses Makmur", "sektor": "Konsumer", "status": "Pengendali", "catatan": ""},
        {"kode": "ICBP", "nama": "Indofood CBP Sukses Makmur", "sektor": "Konsumer", "status": "Pengendali", "catatan": ""},
        {"kode": "SIMP", "nama": "Salim Ivomas Pratama", "sektor": "Perkebunan / CPO", "status": "Pengendali", "catatan": ""},
        {"kode": "LSIP", "nama": "PP London Sumatra Indonesia", "sektor": "Perkebunan", "status": "Pengendali", "catatan": ""},
        {"kode": "IMAS", "nama": "Indomobil Sukses Internasional", "sektor": "Otomotif", "status": "Pengendali", "catatan": ""},
        {"kode": "DNET", "nama": "Indoritel Makmur Internasional", "sektor": "Investasi Ritel", "status": "Pengendali", "catatan": ""},
        {"kode": "BINA", "nama": "Bank Ina Perdana", "sektor": "Perbankan", "status": "Pengendali", "catatan": ""},
        {"kode": "CNMA", "nama": "Nusantara Sejahtera Raya (Cinema XXI)", "sektor": "Bioskop / Hiburan", "status": "Afiliasi", "catatan": ""},
        {"kode": "PANI", "nama": "Pantai Indah Kapuk Dua", "sektor": "Properti", "status": "Pengendali (JV)", "catatan": "Patungan dengan Agung Sedayu (Aguan)"},
        {"kode": "CBDK", "nama": "Bangun Kosambi Sukses", "sektor": "Properti", "status": "Pengendali (JV)", "catatan": "Anak usaha PANI, patungan dengan Agung Sedayu"},
        {"kode": "EMTK", "nama": "Elang Mahkota Teknologi", "sektor": "Media / Teknologi", "status": "Minoritas", "catatan": "Kepemilikan Salim sekitar 15%"},
        {"kode": "AHAP", "nama": "Asuransi Harta Aman Pratama", "sektor": "Asuransi Umum", "status": "Pengendali", "catatan": "Via Asuransi Central Asia 62,57% (Anthoni Salim Komisaris Utama ACA); direksi/komisaris mundur berjamaah 2023"},
        {"kode": "ROTI", "nama": "Nippon Indosari Corpindo", "sektor": "Konsumer (Sari Roti)", "status": "Afiliasi", "catatan": "Anthoni Salim & Wendy Yap tercatat beneficial owner; persentase terkini tidak dipublikasikan spesifik"},
        {"kode": "DCII", "nama": "DCI Indonesia", "sektor": "Data Center", "status": "Minoritas", "catatan": "Anthoni Salim ~11,12%, bukan pengendali (pengendali: Otto Toto Sugiri & Marina Budiman)"},
        {"kode": "AMMN", "nama": "Amman Mineral Internasional", "sektor": "Pertambangan (Tembaga & Emas)", "status": "Minoritas (dulu Pengendali)", "catatan": "Kendali beralih ke entitas Singapura sejak Nov 2024; Salim terus melepas saham sepanjang 2026, sisa eksposur ~6% per akhir 2025"},
    ],
    "Prayogo Pangestu": [
        {"kode": "BRPT", "nama": "Barito Pacific", "sektor": "Holding Energi & Petrokimia", "status": "Pengendali", "catatan": ""},
        {"kode": "TPIA", "nama": "Chandra Asri Pacific", "sektor": "Petrokimia", "status": "Pengendali", "catatan": ""},
        {"kode": "BREN", "nama": "Barito Renewables Energy", "sektor": "Energi Terbarukan / Panas Bumi", "status": "Pengendali", "catatan": ""},
        {"kode": "CUAN", "nama": "Petrindo Jaya Kreasi", "sektor": "Batu Bara", "status": "Pengendali", "catatan": ""},
        {"kode": "PTRO", "nama": "Petrosea", "sektor": "Kontraktor Tambang", "status": "Pengendali", "catatan": "Dikendalikan lewat CUAN"},
        {"kode": "CDIA", "nama": "Chandra Daya Investasi", "sektor": "Infrastruktur & Utilitas", "status": "Pengendali", "catatan": "IPO Juli 2025, spin-off dari TPIA"},
    ],
    "Hapsoro": [
        {"kode": "RAJA", "nama": "Rukun Raharja", "sektor": "Energi / Gas", "status": "Pengendali", "catatan": ""},
        {"kode": "RATU", "nama": "Raharja Energi Cepu", "sektor": "Minyak & Gas", "status": "Pengendali", "catatan": "Anak usaha RAJA"},
        {"kode": "BUVA", "nama": "Bukit Uluwatu Villa", "sektor": "Perhotelan", "status": "Afiliasi", "catatan": ""},
        {"kode": "IATA", "nama": "Indonesia Transport & Infrastructure", "sektor": "Transportasi", "status": "Afiliasi", "catatan": ""},
        {"kode": "MINA", "nama": "Sanurhasta Mitra", "sektor": "Properti (Resort/Villa Bali)", "status": "Pengendali", "catatan": "Via Basis Utama Prima ~30,48% + kepemilikan langsung ~19,68%"},
        {"kode": "SINI", "nama": "Singaraja Putra", "sektor": "Akomodasi / Kayu / Jasa Tambang", "status": "Afiliasi", "catatan": "Pemegang saham terbesar kedua via Basis Energi Prima (>9%) + langsung ~3,89%"},
        {"kode": "UANG", "nama": "Pakuan", "sektor": "Properti & Rekreasi", "status": "Afiliasi", "catatan": "19,35% saham (Nov 2025), pemegang saham terbesar kedua"},
    ],
    "Aguan": [
        {"kode": "PANI", "nama": "Pantai Indah Kapuk Dua", "sektor": "Properti", "status": "Pengendali (JV)", "catatan": "Patungan Agung Sedayu dengan Grup Salim"},
        {"kode": "CBDK", "nama": "Bangun Kosambi Sukses", "sektor": "Properti", "status": "Pengendali (JV)", "catatan": "Pengelola CBD PIK 2"},
        {"kode": "SCBD", "nama": "Danayasa Arthatama", "sektor": "Properti / Perhotelan", "status": "Minoritas", "catatan": "Pemilik kawasan SCBD; kepemilikan Aguan sekitar 7%"},
        {"kode": "INPC", "nama": "Bank Artha Graha Internasional", "sektor": "Perbankan", "status": "Minoritas", "catatan": "Kepemilikan langsung sekitar 2%"},
        {"kode": "ERAA", "nama": "Erajaya Swasembada", "sektor": "Ritel & Distribusi Telekomunikasi", "status": "Pengendali", "catatan": "Via Eralink International 55,17%; UBO Rebecca Halim (istri Aguan) 32,04% + Aguan langsung 13,79%"},
        {"kode": "ERAL", "nama": "Sinar Eka Selaras", "sektor": "Ritel Elektronik & Apparel", "status": "Pengendali", "catatan": "Anak usaha ERAA (79,9998%), terafiliasi Agung Sedayu lewat rantai kepemilikan ERAA"},
    ],
    "Sinarmas": [
        {"kode": "SMMA", "nama": "Sinar Mas Multiartha", "sektor": "Jasa Keuangan", "status": "Pengendali", "catatan": ""},
        {"kode": "BSIM", "nama": "Bank Sinarmas", "sektor": "Perbankan", "status": "Pengendali", "catatan": ""},
        {"kode": "DSSA", "nama": "Dian Swastatika Sentosa", "sektor": "Energi & Digital", "status": "Pengendali", "catatan": "Masuk indeks MSCI Indonesia Global Standard (Agustus 2025)"},
        {"kode": "GEMS", "nama": "Golden Energy Mines", "sektor": "Batu Bara", "status": "Pengendali", "catatan": ""},
        {"kode": "INKP", "nama": "Indah Kiat Pulp & Paper", "sektor": "Pulp & Kertas", "status": "Pengendali", "catatan": ""},
        {"kode": "TKIM", "nama": "Pabrik Kertas Tjiwi Kimia", "sektor": "Pulp & Kertas", "status": "Pengendali", "catatan": ""},
        {"kode": "SMAR", "nama": "SMART", "sektor": "Perkebunan / CPO", "status": "Pengendali", "catatan": ""},
        {"kode": "BSDE", "nama": "Bumi Serpong Damai", "sektor": "Properti", "status": "Pengendali", "catatan": ""},
        {"kode": "DUTI", "nama": "Duta Pertiwi", "sektor": "Properti", "status": "Pengendali", "catatan": "Anak usaha BSDE"},
        {"kode": "DMAS", "nama": "Puradelta Lestari", "sektor": "Properti — Kawasan Industri", "status": "Pengendali", "catatan": "Via Sumber Arus Mulia/Sinar Mas Land 57,28%; mitra JV Sojitz Jepang 25%"},
        {"kode": "EXCL", "nama": "XLSmart Telecom Sejahtera (eks XL Axiata)", "sektor": "Telekomunikasi Seluler", "status": "Pengendali", "catatan": "Sinarmas ambil alih 66,25% dari Axiata April 2025 + merger dgn Smartfren; Axiata masih pengendali bersama"},
    ],
    "Thohir Group": [
        {"kode": "ADRO", "nama": "Alamtri Resources Indonesia (d/h Adaro Energy)", "sektor": "Batu Bara / Energi", "status": "Pengendali", "catatan": ""},
        {"kode": "AADI", "nama": "Adaro Andalan Indonesia", "sektor": "Batu Bara Termal", "status": "Pengendali", "catatan": "Spin-off dari ADRO, listing Desember 2024"},
        {"kode": "ADMR", "nama": "Adaro Minerals Indonesia", "sektor": "Kokas / Aluminium", "status": "Pengendali", "catatan": ""},
        {"kode": "MDKA", "nama": "Merdeka Copper Gold", "sektor": "Emas & Tembaga", "status": "Pemegang Saham Utama", "catatan": "Garibaldi Thohir salah satu pendiri"},
        {"kode": "MBMA", "nama": "Merdeka Battery Materials", "sektor": "Nikel / Bahan Baterai", "status": "Afiliasi", "catatan": "Anak usaha MDKA"},
        {"kode": "ABBA", "nama": "Mahaka Media", "sektor": "Media", "status": "Afiliasi", "catatan": "Kepemilikan keluarga Thohir berubah sejak Erick Thohir menjabat menteri"},
        {"kode": "MARI", "nama": "Mahaka Radio Integra", "sektor": "Media / Radio", "status": "Afiliasi", "catatan": ""},
        {"kode": "BFIN", "nama": "BFI Finance Indonesia", "sektor": "Pembiayaan / Multifinance", "status": "Pengendali", "catatan": "Via Trinugraha Capital bersama Jerry Ng, 51,12%"},
        {"kode": "ESSA", "nama": "ESSA Industries Indonesia", "sektor": "Energi & Kimia (LPG/Amoniak)", "status": "Afiliasi", "catatan": "Bukan pengendali; Boy Thohir individu ~13,41% (menyusut), pengendali resmi kini Chander Vinod Laroya 18,88%"},
    ],
    "Djarum Group": [
        {"kode": "BBCA", "nama": "Bank Central Asia", "sektor": "Perbankan", "status": "Pengendali", "catatan": ""},
        {"kode": "TOWR", "nama": "Sarana Menara Nusantara", "sektor": "Menara Telekomunikasi", "status": "Pengendali", "catatan": ""},
        {"kode": "SUPR", "nama": "Solusi Tunas Pratama", "sektor": "Menara Telekomunikasi", "status": "Pengendali", "catatan": "Anak usaha TOWR"},
        {"kode": "BELI", "nama": "Global Digital Niaga (Blibli)", "sektor": "E-commerce", "status": "Pengendali", "catatan": ""},
        {"kode": "GOTO", "nama": "GoTo Gojek Tokopedia", "sektor": "Teknologi", "status": "Minoritas", "catatan": "Kepemilikan minoritas lewat entitas grup"},
        {"kode": "DATA", "nama": "Remala Abadi", "sektor": "Internet Service Provider", "status": "Pengendali", "catatan": "Protelindo (anak usaha TOWR) kuasai 51% setelah akuisisi Juli 2026"},
        {"kode": "HEAL", "nama": "Medikaloka Hermina", "sektor": "Rumah Sakit", "status": "Minoritas", "catatan": "Dwimuria Investama Andalan (kendaraan Hartono, juga pengendali BBCA) ~3,64%, bukan pengendali"},
        {"kode": "RANC", "nama": "Supra Boga Lestari", "sektor": "Ritel — Supermarket Premium", "status": "Pengendali", "catatan": "Via Global Digital Niaga/Blibli 70,56% (Ranch Market, Farmers Market)"},
    ],
    "Low Tuck Kwong": [
        {"kode": "BYAN", "nama": "Bayan Resources", "sektor": "Batu Bara", "status": "Pengendali", "catatan": "Emiten utama; sebagian besar aset lain tidak tercatat di BEI"},
    ],
    "Lippo Group": [
        {"kode": "LPKR", "nama": "Lippo Karawaci", "sektor": "Properti", "status": "Pengendali", "catatan": ""},
        {"kode": "LPCK", "nama": "Lippo Cikarang", "sektor": "Properti", "status": "Pengendali", "catatan": ""},
        {"kode": "SILO", "nama": "Siloam International Hospitals", "sektor": "Kesehatan", "status": "Afiliasi", "catatan": "Kepemilikan berubah setelah masuknya investor strategis"},
        {"kode": "MPPA", "nama": "Matahari Putra Prima", "sektor": "Ritel", "status": "Pengendali", "catatan": ""},
        {"kode": "MLPL", "nama": "Multipolar", "sektor": "Investasi / Teknologi", "status": "Pengendali", "catatan": ""},
        {"kode": "MLPT", "nama": "Multipolar Technology", "sektor": "Teknologi Informasi", "status": "Pengendali", "catatan": ""},
        {"kode": "NOBU", "nama": "Bank Nationalnobu", "sektor": "Perbankan", "status": "Pengendali", "catatan": ""},
        {"kode": "GMTD", "nama": "Gowa Makassar Tourism Development", "sektor": "Properti", "status": "Pengendali", "catatan": ""},
        {"kode": "LPPF", "nama": "Matahari Department Store", "sektor": "Ritel", "status": "Minoritas", "catatan": "Kepemilikan Lippo sudah sangat menyusut"},
    ],
    "Hasyim": [
        {"kode": "WIFI", "nama": "Solusi Sinergi Digital (Surge)", "sektor": "Teknologi / Infrastruktur Digital", "status": "Pengendali", "catatan": "Dikendalikan lewat PT Investasi Sukses Bersama / Arsari"},
        {"kode": "COIN", "nama": "Indokripto Koin Semesta", "sektor": "Aset Digital / Kripto", "status": "Minoritas", "catatan": "Arsari Nusa Investama masuk sebagai pemegang saham (Des 2025)"},
    ],
    "Kawan Lama Group": [
        {"kode": "ACES", "nama": "Aspirasi Hidup Indonesia (AZKO)", "sektor": "Ritel", "status": "Pengendali", "catatan": "Sebagian besar unit usaha grup lain tidak tercatat di BEI"},
    ],
    "Harita Group": [
        {"kode": "NCKL", "nama": "Trimegah Bangun Persada", "sektor": "Nikel", "status": "Pengendali", "catatan": ""},
        {"kode": "CITA", "nama": "Cita Mineral Investindo", "sektor": "Bauksit & Alumina", "status": "Pengendali", "catatan": ""},
    ],
    "Astra Group": [
        {"kode": "ASII", "nama": "Astra International", "sektor": "Konglomerasi / Otomotif", "status": "Induk", "catatan": ""},
        {"kode": "UNTR", "nama": "United Tractors", "sektor": "Alat Berat & Tambang", "status": "Pengendali", "catatan": ""},
        {"kode": "AALI", "nama": "Astra Agro Lestari", "sektor": "Perkebunan / CPO", "status": "Pengendali", "catatan": ""},
        {"kode": "AUTO", "nama": "Astra Otoparts", "sektor": "Komponen Otomotif", "status": "Pengendali", "catatan": ""},
        {"kode": "ACST", "nama": "Acset Indonusa", "sektor": "Konstruksi", "status": "Pengendali", "catatan": ""},
    ],
    "Haji Isam Group": [
        {"kode": "JARR", "nama": "Jhonlin Agro Raya", "sektor": "Perkebunan / CPO", "status": "Pengendali", "catatan": "Dikendalikan lewat PT Eshan Agro Sentosa; riwayat UMA & suspensi"},
        {"kode": "PGUN", "nama": "Pradiksi Gunatama", "sektor": "Perkebunan / CPO", "status": "Afiliasi", "catatan": "Riwayat UMA & suspensi BEI"},
        {"kode": "TEBE", "nama": "Dana Brata Luhur", "sektor": "Infrastruktur Penunjang Tambang", "status": "Afiliasi", "catatan": "Kepemilikan lewat PT Dua Samudera"},
        {"kode": "PACK", "nama": "Abadi Nusantara Hijau Investama", "sektor": "Kemasan", "status": "Minoritas", "catatan": "Pembelian 21,12% saham pada Mei 2026"},
        {"kode": "FAST", "nama": "Fast Food Indonesia (KFC)", "sektor": "Restoran", "status": "Minoritas", "catatan": "Pemegang saham lain termasuk Gelael dan Grup Salim"},
    ],
    "Emtek Group": [
        {"kode": "EMTK", "nama": "Elang Mahkota Teknologi", "sektor": "Holding Media & Teknologi", "status": "Induk", "catatan": ""},
        {"kode": "SCMA", "nama": "Surya Citra Media", "sektor": "Media / TV", "status": "Pengendali", "catatan": "Mengoperasikan SCTV, Indosiar, Moji, Vidio"},
        {"kode": "SAME", "nama": "Sarana Meditama Metropolitan", "sektor": "Kesehatan", "status": "Pengendali", "catatan": "Jaringan EMC & Omni Hospital"},
        {"kode": "BUKA", "nama": "Bukalapak.com", "sektor": "E-commerce", "status": "Minoritas", "catatan": "Kepemilikan sekitar 24% lewat Kreatif Media Karya"},
    ],
}
