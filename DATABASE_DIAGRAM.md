# SheMarket — Database Relationship Diagram

```mermaid
erDiagram
    users {
        INT id PK
        VARCHAR full_name
        VARCHAR email UK
        VARCHAR password_hash
        VARCHAR phone UK
        ENUM role
        ENUM status
        VARCHAR profile_image
        DATETIME created_at
        DATETIME updated_at
    }

    businesses {
        INT id PK
        INT owner_id FK UK
        VARCHAR name
        TEXT description
        VARCHAR category
        VARCHAR address
        VARCHAR logo
        ENUM status
        DATETIME created_at
        DATETIME updated_at
    }

    verification_documents {
        INT id PK
        INT business_id FK
        ENUM doc_type
        VARCHAR file_url
        DATETIME uploaded_at
        BOOLEAN is_verified
    }

    products {
        INT id PK
        INT business_id FK
        VARCHAR name
        TEXT description
        DECIMAL price
        INT stock_qty
        VARCHAR category
        ENUM status
        DATETIME created_at
        DATETIME updated_at
    }

    product_images {
        INT id PK
        INT product_id FK
        VARCHAR image_url
        BOOLEAN is_primary
        DATETIME uploaded_at
    }

    carts {
        INT id PK
        INT user_id FK UK
        DATETIME created_at
        DATETIME updated_at
    }

    cart_items {
        INT id PK
        INT cart_id FK
        INT product_id FK
        INT quantity
        DATETIME added_at
    }

    orders {
        INT id PK
        INT user_id FK
        ENUM status
        DECIMAL total_amount
        VARCHAR shipping_address
        DATETIME created_at
        DATETIME updated_at
    }

    order_items {
        INT id PK
        INT order_id FK
        INT product_id FK
        INT quantity
        DECIMAL unit_price
    }

    payments {
        INT id PK
        INT order_id FK UK
        DECIMAL amount
        ENUM method
        ENUM status
        VARCHAR transaction_ref UK
        DATETIME paid_at
        DATETIME created_at
    }

    reviews {
        INT id PK
        INT user_id FK
        INT product_id FK
        TINYINT rating
        TEXT comment
        DATETIME created_at
    }

    users ||--o| businesses : "owns"
    businesses ||--o{ verification_documents : "has"
    businesses ||--o{ products : "lists"
    products ||--o{ product_images : "has"
    users ||--o| carts : "has"
    carts ||--o{ cart_items : "contains"
    products ||--o{ cart_items : "in"
    users ||--o{ orders : "places"
    orders ||--o{ order_items : "contains"
    products ||--o{ order_items : "in"
    orders ||--o| payments : "paid via"
    users ||--o{ reviews : "writes"
    products ||--o{ reviews : "receives"
```

## Relationship Summary

| Relationship | Cardinality | Notes |
|---|---|---|
| User → Business | 1 : 0..1 | One owner, one business |
| Business → VerificationDocument | 1 : N | Multiple docs per business |
| Business → Product | 1 : N | Business lists many products |
| Product → ProductImage | 1 : N | One primary + extras |
| User → Cart | 1 : 1 | One cart per user |
| Cart → CartItem | 1 : N | Many items in cart |
| CartItem → Product | N : 1 | Each item links one product |
| User → Order | 1 : N | User places many orders |
| Order → OrderItem | 1 : N | Snapshot at purchase time |
| OrderItem → Product | N : 1 | Preserves unit_price |
| Order → Payment | 1 : 1 | One payment per order |
| User → Review | 1 : N | User reviews many products |
| Product → Review | 1 : N | One review per user per product (UNIQUE) |
