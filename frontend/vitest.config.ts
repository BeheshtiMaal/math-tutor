import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
export default defineConfig({plugins:[react()],resolve:{alias:{"@":path.resolve(import.meta.dirname,".")}},test:{pool:"threads",maxWorkers:1,fileParallelism:false,environment:"happy-dom",setupFiles:["./tests/setup.ts"],include:["tests/**/*.test.ts","tests/**/*.test.tsx"]}});
