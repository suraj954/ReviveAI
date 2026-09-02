function Navbar() {
  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="brand">
          <div className="brand-mark">
            R
          </div>

          <div className="brand-text">
            <span className="brand-name">
              Revive Store
            </span>
            <span className="brand-subtitle">
              Powered by ReviveAI
            </span>
          </div>
        </div>

        <div className="nav-links">
          <a href="#products">Products</a>
          <a href="#how-it-works">How it works</a>

          <span className="ai-status">
            <span className="status-dot" />
            AI Recovery Active
          </span>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;