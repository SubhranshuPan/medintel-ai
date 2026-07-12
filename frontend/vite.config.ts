import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// React + Tailwind v4 (Vite plugin, no separate tailwind.config needed for base use).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
});
