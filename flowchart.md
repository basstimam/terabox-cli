flowchart TD
    A[Start] --> B[Inisialisasi TeraboxDownloader]
    B --> C[Tampilkan Banner]
    C --> D{Cek URL Input}
    
    D -->|Valid| E[Process URL]
    D -->|Invalid| Z[Exit dengan Error]
    
    E --> F[Parse & Validasi URL]
    F --> G[Ambil Info File dari Terabox]
    G --> H[Tampilkan Daftar File]
    
    H --> I{Pilihan User}
    
    I -->|Download All| J[Download Semua File]
    I -->|Single File| K[Download File Tunggal]
    
    J --> L[Flatten File Structure]
    L --> M[Buat Folder]
    M --> N[Loop Setiap File]
    
    K --> O{Cek aria2}
    O -->|Tersedia| P[Download dengan aria2]
    O -->|Tidak Tersedia| Q[Download Default]
    
    N --> O
    
    P --> R[Verifikasi File]
    Q --> R
    
    R --> S{Download Selesai?}
    S -->|Ya| T[Update Progress]
    S -->|Tidak| U[Retry Download]
    U --> O
    
    T --> V{Semua File Selesai?}
    V -->|Ya| W[Tampilkan Ringkasan]
    V -->|Tidak| N
    
    W --> X[End]
    
    subgraph "Error Handling"
        EA[Error Detected] --> EB{Jenis Error}
        EB -->|Network| EC[Retry dengan Backoff]
        EB -->|File System| ED[Log Error]
        EB -->|Fatal| EE[Exit Program]
        EC --> O
    end
    
    subgraph "Progress Tracking"
        PA[Update Progress Bar]
        PB[Log Activity]
        PC[Speed Monitor]
    end