### User usage flow
```mermaid
%%{init: {'theme':'base', 'themeVariables': {'fontSize':'18px', 'fontFamily':'Arial'}}}%%
graph LR
    A["🖱️ <b>Kích hoạt</b><br/>(Client)<br/><br/>Người dùng<br/>nhấn nút 'Verify'<br/>trong bài đăng <br/> trên mạng xã hội"]

    B["🔍 <b>Truy xuất</b><br/>(Backend)<br/><br/>AI trích xuất thông tin<br/>và tìm các bài báo<br/>liên quan nhất<br/>trong cơ sở dữ liệu"]

    C["✅ <b>Xác minh</b><br/>(Backend)<br/><br/>AI phân tích và đối chiếu<br/>từng luận điểm<br/>với bài báo liên quan"]

    D["📊 <b>Tổng hợp</b><br/>(Backend)<br/><br/>Hệ thống tổng<br/>hợp kết quả,<br/>tính độ tin cậy<br/>và đưa ra giải thích"]

    E["📱 <b>Hiển thị</b><br/>(Client)<br/><br/>Hiển thị <br/> kết quả xác minh<br/>trên giao diện<br/>người dùng"]

    A ==> B
    B ==> C
    C ==> D
    D ==> E

    classDef clientStyle fill:#fff3e0,stroke:#f57c00,stroke-width:4px,color:#e65100,rx:15,ry:15
    classDef backendStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:4px,color:#1b5e20,rx:15,ry:15

    class A,E clientStyle
    class B,C,D backendStyle
```

### System overview
```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'fontSize':'16px'}}}%%
graph TD
    %% Browser Extension Layer
    subgraph BrowserExt["<b>Browser Extension</b>"]
        direction TB
        ContentScript["<b>Content script</b><br/><i>Trích xuất <br> nội dung bài đăng</i>"]
        ResultsPanel["<b>Bảng kết quả</b><br/><i>Hiển thị kết quả xác minh <br> & giải thích chi tiết</i>"]
    end

    %% Backend API Layer
    subgraph BackendAPI["<b>API Backend (FastAPI)</b>"]
        direction TB

        Orchestrator["<b>Bộ điều phối xác minh</b><br/>"]

        subgraph Pipeline["<b>Luồng kiểm chứng</b>"]
            direction LR

            Retrieval["<b>Truy xuất</b><br/><div style='text-align:left'>• Làm sạch nội dung<br/>• Tách luận điểm & thực thể<br/>• Tìm kiếm kết hợp <br>  (Vector, BM25)<br/>• Xếp hạng bài báo theo mức độ liên quan</div>"]
            Verification["<b>Xác minh</b><br/><div style='text-align:left'>• Phân tích lập trường (NLI)<br/>• Giải thích chi tiết<br/>• Tổng hợp kết quả</div>"]

            Retrieval ==> Verification
        end

        Orchestrator ==> Pipeline
    end

    %% Data Layer (Left Side)
    subgraph DataLayer["<b>Lớp dữ liệu</b>"]
        direction TB
        Cache["<b>Bộ nhớ đệm Redis</b><br/><i>TTL 24h</i>"]
        Database["<b>PostgreSQL</b><br/><div style='text-align:left'>• CSDL vector (pgvector)<br/>• CSDL bài viết (FTS)</div>"]
    end

    %% External AI (Right Side)
    OpenAI["<b>🤖 API OpenAI</b><br/><div style='text-align:left'>• text-embedding-3-small<br/>• GPT-4o-mini</div>"]

    %% Data Crawler (Background)
    subgraph CrawlerPipeline["<b>Thu thập dữ liệu</b> <br> <i>(Tự động chạy nền mỗi giờ)</i>"]
        direction LR
        Crawl["<b>Thu thập & quét</b><br/><i>RSS → Nội dung</i>"]
        Process["<b>Xử lý & lập chỉ mục</b><br/><i>Chunk → Nhúng → Index</i>"]

        Crawl --> Process
    end

    %% External Sources (Bottom)
    RSSFeeds["<b>📰 Nguồn tin uy tín</b><br/><i>Hơn 100 RSS Feed</i><br/>Thanh Niên, Tuổi Trẻ, v.v."]

    %% Main Verification Flow
    ContentScript ==>|POST /verify| Orchestrator
    Orchestrator -->|Kiểm tra cache| Cache
    Orchestrator ==>|Phản hồi| ResultsPanel

    Pipeline -->|Tìm kiếm| Database
    Pipeline -->|Trích xuất, xếp hạng, xác minh| OpenAI

    %% Background Crawler Flow
    RSSFeeds -.->|Lấy RSS| Crawl
    Crawl -.->|Tạo embeddings| OpenAI
    OpenAI -.->|Vector| Process
    Process -.->|Lưu trữ| Database

    %% Styling
    classDef browserStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10
    classDef apiStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,color:#1b5e20,rx:10,ry:10
    classDef crawlerStyle fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#f57f17,rx:10,ry:10
    classDef dataStyle fill:#fce4ec,stroke:#c2185b,stroke-width:3px,color:#880e4f,rx:10,ry:10
    classDef externalStyle fill:#e0f2f1,stroke:#00897b,stroke-width:2px,color:#004d40,rx:8,ry:8
    classDef pipelineStyle fill:#f5f5f5,stroke:#9e9e9e,stroke-width:2px,stroke-dasharray:5 5,rx:10,ry:10
    classDef nodeStyle fill:#ffffff,stroke:#424242,stroke-width:2px,color:#212121,rx:8,ry:8
    classDef orchestratorStyle fill:#ffecb3,stroke:#ff6f00,stroke-width:3px,color:#e65100,rx:8,ry:8

    class BrowserExt browserStyle
    class BackendAPI apiStyle
    class CrawlerPipeline crawlerStyle
    class DataLayer dataStyle
    class RSSFeeds,OpenAI externalStyle
    class Pipeline pipelineStyle
    class ContentScript,ResultsPanel,Crawl,Process,Cache,Database nodeStyle
    class Retrieval,Verification nodeStyle
    class Orchestrator orchestratorStyle
```

### Verification pipeline (Luồng kiểm chứng thông tin)

```mermaid
---
config:
  theme: base
  themeVariables:
    fontSize: 16px
    fontFamily: Arial
  layout: dagre
---
flowchart LR
    Claims["🧩 <b>Luận điểm</b><br><i>Đã trích xuất từ bài đăng</i>"]
    Evidence["📚 <b>Bài báo liên quan</b><br><i>Kết quả từ retrieval pipeline</i>"]
    Pair["🔗 <b>Ghép (luận điểm, đoạn báo)</b><br><i>Chọn các đoạn phù hợp nhất</i>"]
    NLI["🧠 <b>Phân tích lập trường</b><br><i>SUPPORTS / REFUTES / NOT_ENOUGH_INFO + confidence</i>"]
    ClaimAgg["⚖️ <b>Gộp kết quả theo luận điểm</b><br><i>Kết luận + độ tin cậy từng luận điểm</i>"]
    PostAgg["📊 <b>Kết luận toàn bài đăng</b><br><i>FULLY_SUPPORTED / PARTIALLY_SUPPORTED / REFUTED / NOT_ENOUGH_INFO</i>"]

    Signals["🌡️ <b>Các tín hiệu tin cậy</b><br><i>C, S, K, T trên thang 0–1</i>"]
    EvidenceQ["📈 <b>Chất lượng bằng chứng (C)</b><br><i>Trung bình confidence</i>"]
    SourceAgree["🤝 <b>Đồng thuận nguồn tin (S)</b><br><i>Tỷ lệ nhãn đa số</i>"]
    Coverage["🧮 <b>Độ bao phủ luận điểm (K)</b><br><i>% luận điểm được ủng hộ</i>"]
    TimeRel["⏱️ <b>Độ mới thời gian (T)</b><br><i>Tuổi bài báo</i>"]
    Score["⭐ <b>Điểm tin cậy tổng</b><br><i>overall_confidence 0–1</i>"]
    Bucket["🎨 <b>Mức hiển thị cho người dùng</b><br><i>HIGH / MEDIUM / LOW / NONE</i>"]

    Claims & Evidence --> Pair --> NLI --> ClaimAgg --> PostAgg
    ClaimAgg --> Signals
    Signals --> EvidenceQ & SourceAgree & Coverage & TimeRel
    EvidenceQ & SourceAgree & Coverage & TimeRel --> Score --> Bucket

    classDef stepStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1,rx:10,ry:10
    classDef dataStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10

    class Claims,Evidence,Signals,Bucket dataStyle
    class Pair,NLI,ClaimAgg,PostAgg,EvidenceQ,SourceAgree,Coverage,TimeRel,Score stepStyle
```

### Retrieval pipeline (Luồng truy xuất thông tin)

```mermaid
---
config:
  theme: base
  themeVariables:
    fontSize: 16px
    fontFamily: Arial
  layout: dagre
---
flowchart LR
    Input["📝 <b>Văn bản bài đăng</b><br>(đã được Orchestrator chuẩn hóa)"] --> Claims["🧩 <b>Trích xuất luận điểm</b><br><i>Lấy luận điểm, từ khóa, thực thể</i>"]
    Claims --> Embedding["🔢 <b>Sinh embedding</b><br><i>Vector ngữ nghĩa bằng OpenAI</i>"] & BM25Search["🔎 <b>Full-text search (BM25)</b><br><i>PostgreSQL FTS – từ khóa quan trọng</i>"]
    Embedding --> VectorSearch["📐 <b>Vector search</b><br><i>pgvector – đo độ tương đồng ngữ nghĩa</i>"]
    VectorSearch --> Fusion["⚖️ <b>Hợp nhất &amp; xếp hạng</b><br><i>Kết hợp điểm vector + BM25</i>"]
    BM25Search --> Fusion
    Fusion --> Output["📚 <b>Danh sách bài báo</b><br><i>Kèm điểm liên quan</i>"]

     Input:::dataStyle
     Claims:::stepStyle
     Embedding:::stepStyle
     BM25Search:::stepStyle
     VectorSearch:::stepStyle
     Fusion:::stepStyle
     Output:::dataStyle
    classDef stepStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1,rx:10,ry:10
    classDef dataStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10
```

### Data ingestion pipeline (Luồng nạp dữ liệu)

```mermaid
---
config:
  theme: base
  themeVariables:
    fontSize: 16px
    fontFamily: Arial
  layout: dagre
---
flowchart LR
    Sources["📰 <b>Nguồn tin uy tín</b><br><i>Hơn 100 RSS feed</i>"]
    Fetch["📡 <b>Thu RSS định kỳ</b><br><i>Celery Beat scheduler</i>"]
    Extract["🧾 <b>Trích xuất nội dung</b><br><i>Lọc HTML, bỏ nhiễu</i>"]
    Chunk["✂️ <b>Chia đoạn văn bản</b><br><i>Chunk 500–2000 ký tự</i>"]
    Embed["🔢 <b>Sinh embedding</b><br><i>Vector ngữ nghĩa bằng OpenAI</i>"]
    Store["💾 <b>Lưu &amp; lập chỉ mục</b><br><i>PostgreSQL + pgvector + FTS</i>"]
    Cleanup["🗑️ <b>Dọn dẹp bài cũ</b><br><i>Xóa bản ghi &gt; 24 giờ</i>"]
    Knowledge["📚 <b>Kho dữ liệu phục vụ truy xuất</b><br><i>Retrieval pipeline sử dụng</i>"]

    Sources --> Fetch --> Extract --> Chunk --> Embed --> Store --> Cleanup
    Store --> Knowledge

    classDef stepStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1,rx:10,ry:10
    classDef dataStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10

    class Sources,Knowledge dataStyle
    class Fetch,Extract,Chunk,Embed,Store,Cleanup stepStyle
```

### Caching pipeline (Luồng cache tối ưu thời gian phản hồi)

```mermaid
---
config:
  theme: base
  themeVariables:
    fontSize: 16px
    fontFamily: Arial
  layout: dagre
---
flowchart LR
    Post["📝 <b>Bài đăng cần kiểm chứng</b><br><i>Nội dung văn bản đầy đủ</i>"]
    Hash["🔐 <b>Tính mã băm nội dung</b><br><i>SHA-256(post_text)</i>"]
    Check["📦 <b>Kiểm tra cache</b><br><i>Redis: key = hash</i>"]

    Hit["⚡ <b>Cache hit</b><br><i>Đã có kết quả trước đó</i>"]
    Miss["🐢 <b>Cache miss</b><br><i>Chưa từng xử lý nội dung này</i>"]

    Pipelines["🧠 <b>Chạy đầy đủ pipeline</b><br><i>Truy vấn + Xác minh</i>"]
    Save["💾 <b>Lưu kết quả vào Redis</b><br><i>TTL ≈ 24 giờ</i>"]
    Result["📱 <b>Trả kết quả cho người dùng</b><br><i>Kết luận + điểm tin cậy + giải thích</i>"]

    Post --> Hash --> Check
    Check -->|Có trong cache| Hit --> Result
    Check -->|Không có| Miss --> Pipelines --> Save --> Result

    classDef stepStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1,rx:10,ry:10
    classDef dataStyle fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100,rx:10,ry:10

    class Post,Result dataStyle
    class Hash,Check,Hit,Miss,Pipelines,Save stepStyle
```

### 6. Tổng quan hệ thống

#### 6.1 Thành phần

- **Đầu vào**: Người dùng Facebook chọn bài đăng cần kiểm chứng từ giao diện mạng xã hội.
- **Client (Chrome Extension MV3)**: Content script đọc nội dung bài đăng, popup/modal hiển thị kết quả và gửi yêu cầu `POST /verify` tới backend qua `chrome.runtime.sendMessage`.
- **Backend (FastAPI + workers)**: Service orchestrator thực thi chuỗi 9 bước: trích xuất truy vấn/luận điểm, tạo embedding bằng OpenAI `text-embedding-3-small`, truy xuất lai (pgvector + BM25), RRF fusion, rerank 100 đoạn bằng LLM, gộp theo bài báo, rerank cấp bài báo, tính điểm tin cậy đa tín hiệu và chặn kết quả dưới ngưỡng.
- **Cache & CSDL**: Redis lưu kết quả truy xuất trong 24h để tránh xử lý lại; PostgreSQL + pgvector lưu bài báo gốc, metadata và vector embedding.
- **Crawler**: Celery workers thu thập RSS chính thống, cắt đoạn–nhúng–lập chỉ mục; Celery Beat scheduler (chu kỳ mặc định 5 phút, điều chỉnh trong `backend/config/config.yaml`) đảm bảo dữ liệu luôn mới.

#### 6.2 Luồng dữ liệu

Bài đăng ➜ Content script ➜ Backend `/verify` (Embedding ➜ Truy xuất ➜ Tính điểm) ➜ Redis/PostgreSQL ➜ Modal hiển thị kết quả.

#### 6.3 Backend & pipeline

- **Tiếp nhận & kiểm tra trùng lặp**: API `/verify` nhận bài đăng, tạo phiên làm việc async và kiểm tra nhanh trong Redis xem bài này đã được xử lý trong 24 giờ gần nhất hay chưa. Nếu tìm thấy, hệ thống trả về kết quả tức thì nhưng vẫn chạy lại bước đánh giá để đảm bảo lập luận và cảnh báo luôn mới.
- **Truy xuất nhiều tầng**: Khi không có cache, backend khởi động chuỗi 9 bước gồm trích xuất truy vấn/luận điểm, tạo embedding OpenAI, truy xuất lai giữa pgvector và BM25, hợp nhất kết quả bằng Reciprocal Rank Fusion, rồi dùng LLM để sắp xếp lại 100 đoạn văn bản tiềm năng trước khi gộp thành bài báo. Mỗi bước đều có ghi nhận thời gian để theo dõi hiệu năng.
- **Đánh giá độ tin cậy**: Sau khi gộp bài, hệ thống tiếp tục chấm điểm ở cấp bài viết, tính toán các tín hiệu như độ phủ thực thể, sự khác biệt giữa các kết quả và mức độ khớp tiêu đề–nội dung để loại bỏ những đáp án có nguy cơ nhiễu.
- **Xác minh lập luận**: Từ danh sách bài báo cuối cùng, dịch vụ verification ghép từng claim với nguồn liên quan, dùng mô hình lập trường (stance) để xác định ủng hộ hay bác bỏ, tổng hợp thành kết luận chung và tạo lời giải thích tiếng Việt dễ hiểu cho người dùng cuối.

#### 6.4 Đặc điểm kỹ thuật

- Mã hóa văn bản bằng OpenAI embeddings để so khớp ngữ nghĩa, kết hợp truy xuất BM25 cho từ khóa hiếm.
- RRF fusion và reranking bằng GPT-4o-mini bảo đảm các đoạn/bài báo sát nội dung bài đăng trước khi tổng hợp.
- Redis caching giúp trả lời lần lặp lại trong ~ms; luôn có fallback chạy đầy đủ nếu cache miss.
- Celery Beat điều phối crawler định kỳ; interval cấu hình bằng `scheduler.crawler_interval_minutes`.
- Điểm tin cậy đa tín hiệu so sánh với nguồn báo chí, áp dụng trọng số theo độ phủ thực thể, độ giống tiêu đề và căn chỉnh thời gian/vị trí để cảnh báo khi kết quả yếu.

#### 6.5 Mục tiêu

Giúp người dùng xác thực thông tin trên mạng xã hội bằng cách tự động đối chiếu bài đăng với kho bài báo chính thống đã được chuẩn hóa và cập nhật liên tục.
