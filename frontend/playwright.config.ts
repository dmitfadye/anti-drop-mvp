import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:3001', browserName: 'chromium', channel: process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'msedge' },
  webServer: { command: 'npm run start -- --port 3001', url: 'http://127.0.0.1:3001', reuseExistingServer: false, timeout: 60000 },
});
