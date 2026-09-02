export const products = [
  {
    id: 1,
    name: "RevivePods Pro",
    category: "Audio",
    price: 2499,
    description:
      "Premium wireless earbuds with immersive sound and all-day battery life.",
    icon: "🎧",
    badge: "Best Seller",
  },
  {
    id: 2,
    name: "Pulse Watch",
    category: "Wearables",
    price: 3999,
    description:
      "A sleek everyday smartwatch built for productivity, fitness, and style.",
    icon: "⌚",
    badge: "New",
  },
  {
    id: 3,
    name: "Orbit Speaker",
    category: "Audio",
    price: 1799,
    description:
      "Compact portable speaker with rich sound for every space.",
    icon: "🔊",
    badge: null,
  },
  {
    id: 4,
    name: "Nova Keyboard",
    category: "Workspace",
    price: 3299,
    description:
      "A modern mechanical keyboard designed for focused work and creativity.",
    icon: "⌨️",
    badge: "Popular",
  },
];

export function formatPrice(price) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(price);
}