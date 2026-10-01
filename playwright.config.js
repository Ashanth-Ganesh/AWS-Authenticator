const { defineConfig, devices } = require('@playwright/test');
const path = require('node:path');

const python = path.join(__dirname, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

module.exports = defineConfig({
  testDir: './tests/browser',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5001',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `"${python}" -m flask --app backend.app:create_app run --host 127.0.0.1 --port 5001`,
    url: 'http://127.0.0.1:5001/api/health',
    reuseExistingServer: false,
    env: {
      APP_ENV: 'production',
      SECRET_KEY: 'browser-tests-only-session-key',
      COOKIE_SECURE: 'false',
      DATABASE_PATH: path.join(__dirname, 'test-results/browser-users.db'),
    },
  },
});
