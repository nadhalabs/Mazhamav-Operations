import type { Config } from "tailwindcss";
export default { content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"], theme: { extend: { colors: { leaf: { 50: "#f3f8f3", 600: "#287a48", 700: "#1f6139", 900: "#173d29" }, spice: "#d59a35" } } }, plugins: [] } satisfies Config;

