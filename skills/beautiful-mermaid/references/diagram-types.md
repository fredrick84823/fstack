# Mermaid Diagram Types Reference

Complete guide to the 5 diagram types supported by beautiful-mermaid.

---

## 1. Flowcharts

**Use when:** Showing processes, decision trees, workflows, algorithms

**Syntax:** `graph` or `flowchart`

**Directions:**
- `TD` / `TB` - Top to bottom (default)
- `BT` - Bottom to top
- `LR` - Left to right
- `RL` - Right to left

### Basic Example

```mermaid
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Process]
    B -->|No| D[End]
    C --> D
```

### Node Shapes

```mermaid
graph LR
    A[Rectangle]
    B(Rounded)
    C([Stadium])
    D[[Subroutine]]
    E[(Database)]
    F((Circle))
    G>Flag]
    H{Diamond}
    I{{Hexagon}}
    J[/Parallelogram/]
    K[\Parallelogram\]
    L[/Trapezoid\]
    M[\Trapezoid/]
```

### Connection Types

```mermaid
graph LR
    A --- B
    C --> D
    E -.-> F
    G ==> H
    I --o J
    K --x L
    M o--o N
    O x--x P
```

**Legend:**
- `---` Solid line
- `-->` Arrow
- `-.->` Dotted arrow
- `==>` Thick arrow
- `--o` Circle end
- `--x` Cross end
- `o--o` Double circle
- `x--x` Double cross

### Labels

```mermaid
graph TD
    A -->|Label text| B
    C -- Another label --> D
```

---

## Node Shapes Reference

Beautiful-mermaid 支援以下 13 種 node 形狀，每種都有特定的使用情境：

### 基本形狀

```mermaid
graph LR
    A[Rectangle<br/>矩形]
    B(Rounded<br/>圓角矩形)
    C([Stadium<br/>膠囊形])
    D((Circle<br/>圓形))

    A --> B --> C --> D
```

**使用建議**：
- **Rectangle** `[文字]` - 標準流程步驟、一般節點
- **Rounded** `(文字)` - 開始/結束點、強調節點
- **Stadium** `([文字])` - 子流程、模組
- **Circle** `((文字))` - 連接點、狀態節點

### 決策與流程

```mermaid
graph TD
    E{Diamond<br/>菱形決策}
    F{{Hexagon<br/>六邊形}}
    G[/Trapezoid<br/>梯形\]
    H[\Trapezoid Alt<br/>反梯形/]

    E -->|Yes| F
    E -->|No| G
    F --> H
```

**使用建議**：
- **Diamond** `{文字}` - 決策點、條件判斷
- **Hexagon** `{{文字}}` - 準備/初始化步驟
- **Trapezoid** `[/文字\]` - 輸入、手動操作（寬底）
- **Trapezoid Alt** `[\文字/]` - 輸出（寬頂）

### 特殊用途

```mermaid
graph TB
    I[[Subroutine<br/>子程序]]
    J[(Database<br/>資料庫)]
    K>Asymmetric<br/>不對稱旗幟]
    L(((Double Circle<br/>同心圓)))

    I --> J
    J --> K
    K --> L
```

**使用建議**：
- **Subroutine** `[[文字]]` - 子程序、預定義流程
- **Cylinder** `[(文字)]` - 資料庫、資料存儲
- **Asymmetric** `>文字]` - 旗幟、不對稱標記
- **Double Circle** `(((文字)))` - 特殊狀態、結束標記

### 完整範例：美化的工作流程

```mermaid
flowchart TB
    start((開始))
    input[/輸入使用者資料/]
    validate{{驗證資料}}
    decision{資料有效?}
    process[處理請求]
    db[(資料庫)]
    output[\返回結果/]
    error[>錯誤處理]
    sub[[呼叫子程序]]
    end_state(((結束)))

    start --> input
    input --> validate
    validate --> decision
    decision -->|是| process
    decision -->|否| error
    process --> sub
    sub --> db
    db --> output
    output --> end_state
    error --> end_state

    style start fill:#dcfce7,stroke:#22c55e
    style end_state fill:#fecaca,stroke:#ef4444
    style db fill:#dbeafe,stroke:#3b82f6
    style error fill:#fed7aa,stroke:#f97316
```

### 使用 HTML 標籤美化節點

```mermaid
graph LR
    A["<b>粗體標題</b><br/><small>次要說明文字</small>"]
    B["🎨 Beautiful<br/>Mermaid"]
    C["📊 資料分析<br/><small>v1.0.0</small>"]

    A --> B --> C

    style A fill:#fef3c7,stroke:#fbbf24
    style B fill:#e9d5ff,stroke:#a855f7
    style C fill:#dbeafe,stroke:#3b82f6
```

**進階技巧**：
- ✅ 使用 `<br/>` 來分行，提升可讀性
- ✅ 使用 `<small>` 添加次要資訊
- ✅ 使用 `<b>` 強調重要文字
- ✅ 使用 emoji 增加視覺吸引力（適度使用）
- ✅ 使用 `style` 命令自定義顏色

---

### Best Practices

1. **Keep it simple** - Max 10-12 nodes for clarity
2. **Consistent naming** - Use clear, descriptive labels
3. **Logical flow** - Top-down or left-right usually reads best
4. **Group related items** - Use subgraphs for organization
5. **Avoid crossing lines** - Reorganize nodes if lines overlap

---

## 2. State Diagrams

**Use when:** Modeling state machines, application states, lifecycle flows

**Syntax:** `stateDiagram-v2`

### Basic Example

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing: start
    Processing --> Complete: done
    Processing --> Error: fail
    Error --> Idle: retry
    Complete --> [*]
```

### States with Descriptions

```mermaid
stateDiagram-v2
    [*] --> Active
    
    state Active {
        [*] --> Running
        Running --> Paused: pause
        Paused --> Running: resume
        Running --> [*]
    }
    
    Active --> [*]
```

### Composite States

```mermaid
stateDiagram-v2
    [*] --> First
    
    state First {
        [*] --> second
        second --> [*]
    }
    
    state Second {
        [*] --> fir
        fir --> sec
        sec --> [*]
    }
    
    First --> Second
    Second --> [*]
```

### Notes

```mermaid
stateDiagram-v2
    State1: This is a state description
    [*] --> State1
    State1 --> [*]
    
    note right of State1
        Important note here
    end note
```

### Best Practices

1. **Start/End states** - Always use `[*]` for clarity
2. **Transition labels** - Be specific about triggers
3. **Composite states** - Group related states together
4. **Avoid cycles** - Or document them clearly
5. **Limit nesting** - Max 2-3 levels deep

---

## 3. Sequence Diagrams

**Use when:** Showing interactions over time, API calls, message passing

**Syntax:** `sequenceDiagram`

### Basic Example

```mermaid
sequenceDiagram
    participant Alice
    participant Bob
    
    Alice->>Bob: Hello Bob!
    Bob-->>Alice: Hi Alice!
    Alice->>Bob: How are you?
    Bob-->>Alice: Great, thanks!
```

### Arrow Types

```mermaid
sequenceDiagram
    A->>B: Solid arrow
    A-->>B: Dotted arrow
    A-)B: Open arrow
    A--)B: Dotted open arrow
    A-xB: Cross at end
    A--xB: Dotted cross
```

**Usage:**
- `->>`  Request/sync call
- `-->>`  Response
- `-)`  Async message
- `--)`  Async response
- `-x`  Lost message
- `--x`  Lost response

### Activation

```mermaid
sequenceDiagram
    Alice->>+Bob: Request
    Bob->>+Database: Query
    Database-->>-Bob: Data
    Bob-->>-Alice: Response
```

### Loops and Conditions

```mermaid
sequenceDiagram
    Alice->>Bob: Start
    
    loop Every minute
        Bob->>Server: Check status
    end
    
    alt is available
        Server-->>Bob: OK
    else is unavailable
        Server-->>Bob: ERROR
    end
    
    opt Extra check
        Bob->>Server: Verify
    end
```

### Notes

```mermaid
sequenceDiagram
    Alice->>Bob: Message
    Note right of Bob: Bob thinks
    Note over Alice,Bob: Both are thinking
    Bob-->>Alice: Response
```

### Best Practices

1. **Order participants** - Left to right by importance
2. **Activation boxes** - Use `+` and `-` for clarity
3. **Group interactions** - Use alt/loop/opt appropriately
4. **Clear labels** - Describe what's being sent
5. **Limit participants** - 3-5 is ideal, max 7

---

## 4. Class Diagrams

**Use when:** Showing object-oriented structure, database schema, type systems

**Syntax:** `classDiagram`

### Basic Example

```mermaid
classDiagram
    Animal <|-- Duck
    Animal <|-- Fish
    Animal: +String name
    Animal: +int age
    Animal: +isMammal() bool
    
    class Duck {
        +String beakColor
        +swim()
        +quack()
    }
    
    class Fish {
        -int sizeInFeet
        -canEat()
    }
```

### Relationships

```mermaid
classDiagram
    A <|-- B : Inheritance
    C *-- D : Composition
    E o-- F : Aggregation
    G <-- H : Association
    I -- J : Link (solid)
    K <|.. L : Realization
    M <.. N : Dependency
```

**Symbols:**
- `<|--` Inheritance
- `*--` Composition
- `o--` Aggregation
- `<--` Association
- `--` Link
- `<|..` Realization
- `<..` Dependency

### Visibility

```mermaid
classDiagram
    class MyClass {
        +public attribute
        -private attribute
        #protected attribute
        ~package attribute
        +publicMethod()
        -privateMethod()
    }
```

**Modifiers:**
- `+` Public
- `-` Private
- `#` Protected
- `~` Package/Internal

### Cardinality

```mermaid
classDiagram
    Customer "1" --> "*" Order
    Order "1" --> "1..*" LineItem
    LineItem "*" --> "1" Product
```

### Methods and Properties

```mermaid
classDiagram
    class BankAccount {
        +String owner
        +Bigdecimal balance
        +deposit(amount) bool
        +withdrawal(amount) int
    }
```

### Best Practices

1. **Group related classes** - Organize by layer/module
2. **Show key relationships** - Don't model everything
3. **Use cardinality** - Make relationships precise
4. **Visibility matters** - Use +/- appropriately
5. **Limit depth** - 1-2 levels of hierarchy ideal

---

## 5. Entity Relationship (ER) Diagrams

**Use when:** Designing databases, showing data models, relationship mapping

**Syntax:** `erDiagram`

### Basic Example

```mermaid
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "is in"
```

### Relationship Types

```mermaid
erDiagram
    A ||--|| B : "one to one"
    C ||--o{ D : "one to many"
    E }o--o{ F : "many to many"
    G }|--|{ H : "one or more to one or more"
```

**Cardinality symbols:**
- `||` Exactly one
- `o|` Zero or one
- `}o` Zero or more
- `}|` One or more

### Attributes

```mermaid
erDiagram
    CUSTOMER {
        string name
        string email
        int customerId PK
    }
    ORDER {
        int orderId PK
        date orderDate
        int customerId FK
    }
    PRODUCT {
        int productId PK
        string name
        decimal price
    }
    
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : "ordered in"
```

**Attribute keys:**
- `PK` Primary Key
- `FK` Foreign Key

### Complete Example

```mermaid
erDiagram
    USER ||--o{ POST : creates
    USER ||--o{ COMMENT : writes
    POST ||--o{ COMMENT : has
    POST }o--o{ TAG : tagged
    
    USER {
        int userId PK
        string username
        string email
        datetime createdAt
    }
    
    POST {
        int postId PK
        int authorId FK
        string title
        text content
        datetime publishedAt
    }
    
    COMMENT {
        int commentId PK
        int postId FK
        int userId FK
        text content
        datetime createdAt
    }
    
    TAG {
        int tagId PK
        string name
    }
```

### Best Practices

1. **Naming conventions** - UPPERCASE for entities
2. **Show keys** - Always mark PK and FK
3. **Cardinality clarity** - Be precise with relationships
4. **Attribute types** - Include data types
5. **Normalize** - Follow database normalization rules

---

## Choosing the Right Diagram Type

| Diagram Type | Best For | Key Strength |
|-------------|----------|--------------|
| **Flowchart** | Processes, algorithms, workflows | Shows decision paths and flow |
| **State** | State machines, lifecycles | Models state transitions |
| **Sequence** | API interactions, message flow | Shows time-ordered interactions |
| **Class** | OOP structure, type systems | Shows relationships between classes |
| **ER** | Database design, data models | Shows entity relationships |

### Decision Tree

```
Need to show...
├─ A process or workflow? → Flowchart
├─ States and transitions? → State Diagram
├─ Interactions over time? → Sequence Diagram
├─ Class/object structure? → Class Diagram
└─ Database relationships? → ER Diagram
```

---

## General Best Practices

1. **Keep it focused** - One diagram, one concept
2. **Use consistent naming** - CamelCase, snake_case, whatever - be consistent
3. **Add context** - Use notes and comments when needed
4. **Test readability** - Can someone unfamiliar understand it?
5. **Iterate** - Diagrams evolve with understanding
6. **Export early** - Render and review in final format
7. **Version control** - Keep `.mmd` source files in git

---

## Accessibility Tips

1. **Don't rely on color alone** - Use labels and shapes
2. **Provide text alternatives** - Include descriptions
3. **High contrast** - Choose appropriate themes
4. **Font size** - Keep labels readable (beautiful-mermaid handles this)
5. **Simplify** - Less is more for clarity
