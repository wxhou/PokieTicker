// Screenshot Import Selection E2E Tests
// Tests the partial import flow after selecting stocks from screenshot

import { test, expect, Page } from '@playwright/test';
import { writeFileSync } from 'fs';
import { join } from 'path';
import { BasePage } from '../../pages/BasePage';

const BASE_URL = process.env.BASE_URL || 'http://localhost:7777/PokieTicker';

/**
 * ScreenshotImportPage — Page Object for screenshot import modal
 */
class ScreenshotImportPage extends BasePage {
  get openModalBtn() {
    return this.page.getByText('截图导入', { exact: false });
  }
  get closeModalBtn() { return this.page.locator('.si-modal button.si-close'); }
  get selectFileBtn() { return this.page.locator('.si-drop .si-drop-btn', { hasText: '选择文件' }); }
  get cameraBtn() { return this.page.locator('.si-drop .si-drop-btn.primary', { hasText: '拍照' }); }
  get uploadBtn() { return this.page.locator('.si-preview button.primary', { hasText: '确认上传' }); }
  get confirmImportBtn() { return this.page.locator('.si-actions .btn-primary', { hasText: '确认导入' }); }
  get cancelBtn() { return this.page.locator('.si-actions .btn-secondary', { hasText: '取消' }); }
  get loadingIndicator() { return this.page.locator('.si-parsing-text', { hasText: '识别中' }); }
  get toast() { return this.page.locator('.si-toast'); }

  async openModal() {
    await this.openModalBtn.click();
    await expect(this.page.locator('.si-overlay')).toBeVisible({ timeout: 5000 });
  }

  async closeModal() {
    await this.closeModalBtn.click();
    await expect(this.page.locator('.si-overlay')).not.toBeVisible({ timeout: 5000 });
  }

  async uploadFile(filePath: string) {
    const fileInput = this.page.locator('.si-drop input[type="file"]').first();
    await fileInput.setInputFiles(filePath);
  }

  async createTestImage(sizeBytes: number, filename: string): Promise<string> {
    const tmpDir = process.env.TEMP_DIR || '/tmp';
    const filePath = join(tmpDir, filename);
    const pngHeader = Buffer.from([
      0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
      0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
      0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
      0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89,
      0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41, 0x54,
      0x08, 0xD7, 0x63, 0x00, 0x04, 0x00, 0x00, 0x04, 0x00, 0x01,
      0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
    ]);
    const padding = Buffer.alloc(Math.max(0, sizeBytes - pngHeader.length), 0x00);
    const buffer = Buffer.concat([pngHeader, padding]);
    writeFileSync(filePath, buffer);
    return filePath;
  }
}

function createPage(page: Page): ScreenshotImportPage {
  return new ScreenshotImportPage(page);
}

async function login(page: Page) {
  await page.waitForTimeout(500);
  const authCard = page.locator('.portfolio-auth-card');
  try {
    if (await authCard.isVisible({ timeout: 3000 })) {
      await page.fill('input[type="email"]', process.env.E2E_USERNAME || 'e2e@example.com');
      await page.fill('input[type="password"]', process.env.E2E_PASSWORD || 'Test1234!');
      await page.getByRole('button', { name: '登录' }).click();
      await expect(page.locator('.portfolio-page')).toBeVisible({ timeout: 15000 });
    }
  } catch {
    const portfolioPage = page.locator('.portfolio-page');
    if (!(await portfolioPage.isVisible().catch(() => false))) {
      throw new Error('Neither login form nor portfolio page is visible');
    }
  }
}

async function gotoPortfolio(page: Page) {
  await page.goto(BASE_URL + '/');
  await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(() => document.body.textContent?.includes('涨讯'), { timeout: 10000 });

  const portfolioPage = page.locator('.portfolio-page');
  if (await portfolioPage.isVisible({ timeout: 1000 }).catch(() => false)) {
    const closeBtn = page.locator('.si-overlay button.si-close');
    if (await closeBtn.isVisible({ timeout: 500 }).catch(() => false)) {
      await closeBtn.click();
      await page.waitForTimeout(500);
    }
    await expect(portfolioPage).toBeVisible({ timeout: 2000 });
    return;
  }

  const portfolioBtn = page.locator('button:has-text("我的持仓")').first();
  await portfolioBtn.click({ timeout: 5000 });
  await expect(page.locator('.portfolio-page, .portfolio-auth, .portfolio-loading')).toBeVisible({ timeout: 10000 });
  await login(page);
  await expect(portfolioPage).toBeVisible({ timeout: 5000 });
}

// ──────────────────────────────────────────────
// Test Suite: Screenshot Import Selection
// ──────────────────────────────────────────────

test.describe('Screenshot Import Selection', () => {

  test('TC-SEL-1: Confirm button shows selected count', async ({ page }) => {
    const app = createPage(page);
    await gotoPortfolio(page);

    // Mock 3 stocks response
    await page.route('**/api/portfolio/screenshot', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          holdings: [
            { stock_code: '600519', stock_name: '贵州茅台', in_database: true, source: '截图', confidence: 0.9, quantity: null },
            { stock_code: '000001', stock_name: '平安银行', in_database: true, source: '截图', confidence: 0.9, quantity: null },
            { stock_code: '000858', stock_name: '五粮液', in_database: true, source: '截图', confidence: 0.9, quantity: null },
          ],
          unidentified: 0,
          message: '识别成功',
          portfolio_id: 1,
        }),
      });
    });

    await app.openModal();
    const testImagePath = await app.createTestImage(1024, 'test_count.png');
    await app.uploadFile(testImagePath);
    await app.uploadBtn.click();

    // Wait for results
    await page.waitForTimeout(3000);

    // Confirm button should show count
    const confirmBtn = page.locator('.si-actions .btn-primary', { hasText: '确认导入 (3)' });
    await expect(confirmBtn).toBeVisible();
  });

  test('TC-SEL-2: Confirm button disabled when no selection', async ({ page }) => {
    const app = createPage(page);
    await gotoPortfolio(page);

    // Mock 3 stocks response
    await page.route('**/api/portfolio/screenshot', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          holdings: [
            { stock_code: '600519', stock_name: '贵州茅台', in_database: true, source: '截图', confidence: 0.9, quantity: null },
            { stock_code: '000001', stock_name: '平安银行', in_database: true, source: '截图', confidence: 0.9, quantity: null },
          ],
          unidentified: 0,
          message: '识别成功',
          portfolio_id: 1,
        }),
      });
    });

    await app.openModal();
    const testImagePath = await app.createTestImage(1024, 'test_disable.png');
    await app.uploadFile(testImagePath);
    await app.uploadBtn.click();

    // Wait for results
    await page.waitForTimeout(3000);

    // Uncheck all checkboxes
    const checkboxes = page.locator('.si-row input[type="checkbox"]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) {
      await checkboxes.nth(i).uncheck();
    }

    // Confirm button should be disabled
    const confirmBtn = page.locator('.si-actions .btn-primary', { hasText: '确认导入' });
    await expect(confirmBtn).toBeDisabled();
  });

  test('TC-SEL-3: Partial import - uncheck one stock', async ({ page }) => {
    const app = createPage(page);
    await gotoPortfolio(page);

    // Track import API calls
    let importCallCount = 0;
    let lastImportPayload: any = null;

    // Mock screenshot API
    await page.route('**/api/portfolio/screenshot', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          holdings: [
            { stock_code: '600519', stock_name: '贵州茅台', in_database: true, source: '截图', confidence: 0.9, quantity: null },
            { stock_code: '000001', stock_name: '平安银行', in_database: true, source: '截图', confidence: 0.9, quantity: null },
          ],
          unidentified: 0,
          message: '识别成功',
          portfolio_id: 1,
        }),
      });
    });

    // Mock import API
    await page.route('**/api/portfolio/import', async route => {
      importCallCount++;
      const postData = route.request().postDataBuffer();
      if (postData) {
        lastImportPayload = JSON.parse(Buffer.from(postData).toString());
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          imported: lastImportPayload?.stock_codes?.length ?? 0,
          skipped: 0,
          not_found: [],
          message: '导入成功',
        }),
      });
    });

    await app.openModal();
    const testImagePath = await app.createTestImage(1024, 'test_partial.png');
    await app.uploadFile(testImagePath);
    await app.uploadBtn.click();

    // Wait for results
    await page.waitForTimeout(3000);

    // Uncheck first stock
    const firstCheckbox = page.locator('.si-row input[type="checkbox"]').first();
    await firstCheckbox.uncheck();

    // Confirm button count should be 1
    const confirmBtn = page.locator('.si-actions .btn-primary', { hasText: '确认导入 (1)' });
    await expect(confirmBtn).toBeVisible();

    // Click confirm
    await app.confirmImportBtn.click();

    // Wait for response
    await page.waitForTimeout(1000);

    // Verify import API was called with only selected stock
    expect(importCallCount).toBe(1);
    expect(lastImportPayload).not.toBeNull();
    expect(lastImportPayload.stock_codes).toHaveLength(1);
    expect(lastImportPayload.stock_codes).toContain('000001');

    // Modal should close
    await expect(page.locator('.si-overlay')).not.toBeVisible({ timeout: 5000 });
  });

  test('TC-SEL-4: Import API called with stock codes array', async ({ page }) => {
    const app = createPage(page);
    await gotoPortfolio(page);

    let importPayload: any = null;

    // Mock screenshot API
    await page.route('**/api/portfolio/screenshot', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          holdings: [
            { stock_code: '600519', stock_name: '贵州茅台', in_database: true, source: '截图', confidence: 0.9, quantity: null },
            { stock_code: '000858', stock_name: '五粮液', in_database: true, source: '截图', confidence: 0.9, quantity: null },
          ],
          unidentified: 0,
          message: '识别成功',
          portfolio_id: 1,
        }),
      });
    });

    // Mock import API
    await page.route('**/api/portfolio/import', async route => {
      const postData = route.request().postDataBuffer();
      if (postData) {
        importPayload = JSON.parse(Buffer.from(postData).toString());
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          imported: 2,
          skipped: 0,
          not_found: [],
          message: '导入成功',
        }),
      });
    });

    await app.openModal();
    const testImagePath = await app.createTestImage(1024, 'test_api.png');
    await app.uploadFile(testImagePath);
    await app.uploadBtn.click();

    await page.waitForTimeout(3000);

    // Uncheck first stock
    const checkboxes = page.locator('.si-row input[type="checkbox"]');
    await checkboxes.first().uncheck();

    // Click confirm
    await app.confirmImportBtn.click();

    await page.waitForTimeout(1000);

    // Verify payload structure
    expect(importPayload).not.toBeNull();
    expect(importPayload.stock_codes).toBeDefined();
    expect(Array.isArray(importPayload.stock_codes)).toBe(true);
    expect(importPayload.stock_codes).toHaveLength(1);
    expect(importPayload.stock_codes[0]).toBe('000858');
  });

  test('TC-SEL-5: Error handling - import fails gracefully', async ({ page }) => {
    const app = createPage(page);
    await gotoPortfolio(page);

    // Mock screenshot API
    await page.route('**/api/portfolio/screenshot', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          holdings: [
            { stock_code: '600519', stock_name: '贵州茅台', in_database: true, source: '截图', confidence: 0.9, quantity: null },
          ],
          unidentified: 0,
          message: '识别成功',
          portfolio_id: 1,
        }),
      });
    });

    // Mock import API to fail
    await page.route('**/api/portfolio/import', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '服务器错误' }),
      });
    });

    await app.openModal();
    const testImagePath = await app.createTestImage(1024, 'test_error.png');
    await app.uploadFile(testImagePath);
    await app.uploadBtn.click();

    await page.waitForTimeout(3000);

    // Click confirm
    await app.confirmImportBtn.click();

    // Wait for error
    await page.waitForTimeout(1000);

    // Toast should show error
    await expect(app.toast).toBeVisible({ timeout: 3000 });
    await expect(app.toast).toContainText('导入失败');

    // Modal should stay open
    await expect(page.locator('.si-overlay')).toBeVisible();
  });
});