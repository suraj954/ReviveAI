import { formatPrice } from "../data/products";

function ProductCard({ product, onBuy }) {
  return (
    <article className="product-card">
      <div className="product-visual">
        {product.badge && (
          <span className="product-badge">
            {product.badge}
          </span>
        )}

        <div className="product-icon">
          {product.icon}
        </div>
      </div>

      <div className="product-content">
        <p className="product-category">
          {product.category}
        </p>

        <h3>{product.name}</h3>

        <p className="product-description">
          {product.description}
        </p>

        <div className="product-footer">
          <span className="product-price">
            {formatPrice(product.price)}
          </span>

          <button
            className="buy-button"
            onClick={() => onBuy(product)}
          >
            Buy Now
          </button>
        </div>
      </div>
    </article>
  );
}

export default ProductCard;