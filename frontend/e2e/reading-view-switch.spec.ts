/**
 * 阅读视图切换 E2E 测试
 *
 * [INPUT]: 依赖 @playwright/test
 * [OUTPUT]: 对外提供视图切换功能的 E2E 测试
 * [POS]: frontend/e2e 的阅读视图切换测试
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */
import { test, expect } from '@playwright/test';

test.describe('阅读视图切换功能测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5157/reading');
    await page.waitForLoadState('networkidle');
  });

  test('视图切换器显示正确', async ({ page }) => {
    // 验证视图切换器存在
    const listViewButton = page.locator('button:has-text("列表视图")');
    const handoutButton = page.locator('button:has-text("讲义视图")');

    await expect(listViewButton).toBeVisible();
    await expect(handoutButton).toBeVisible();
  });

  test('默认显示列表视图', async ({ page }) => {
    // 验证列表视图按钮被选中
    const listViewButton = page.locator('button:has-text("列表视图")');
    await expect(listViewButton).toHaveAttribute('class', /ant-radio-button-wrapper-checked/);

    // 验证表格存在
    const table = page.locator('.ant-table');
    await expect(table).toBeVisible();
  });

  test('切换到讲义视图', async ({ page }) => {
    // 点击讲义视图
    await page.click('text=讲义视图');

    // 等待视图切换
    await page.waitForTimeout(500);

    // 验证讲义视图按钮被选中
    const handoutButton = page.locator('button:has-text("讲义视图")');
    await expect(handoutButton).toHaveAttribute('class', /ant-radio-button-wrapper-checked/);

    // 验证占位符显示（讲义视图）
    const placeholder = page.locator('text=讲义视图');
    await expect(placeholder).toBeVisible();
  });

  test('切换回列表视图', async ({ page }) => {
    // 切换到讲义视图
    await page.click('text=讲义视图');
    await page.waitForTimeout(500);

    // 切换回列表视图
    await page.click('text=列表视图');
    await page.waitForTimeout(500);

    // 验证表格重新显示
    const table = page.locator('.ant-table');
    await expect(table).toBeVisible();
  });

  test('列表视图功能不受影响', async ({ page }) => {
    // 验证筛选器存在
    const gradeSelect = page.locator('.ant-select:has-text("选择年级")');
    await expect(gradeSelect).toBeVisible();

    // 验证搜索框存在
    const searchInput = page.locator('input[placeholder="搜索文章内容..."]');
    await expect(searchInput).toBeVisible();

    // 验证表格数据加载
    const tableRows = page.locator('.ant-table-tbody tr');
    const rowCount = await tableRows.count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test('快速切换视图不会报错', async ({ page }) => {
    // 快速切换视图5次
    for (let i = 0; i < 5; i++) {
      await page.click('text=讲义视图');
      await page.waitForTimeout(100);
      await page.click('text=列表视图');
      await page.waitForTimeout(100);
    }

    // 验证没有错误提示
    const errorMessage = page.locator('.ant-message-error');
    await expect(errorMessage).not.toBeVisible();
  });
});

test.describe('现有功能回归测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5157/reading');
    await page.waitForLoadState('networkidle');
  });

  test('筛选功能正常', async ({ page }) => {
    // 选择年级
    await page.click('.ant-select:has-text("选择年级")');
    await page.waitForTimeout(300);

    // 验证下拉菜单出现
    const dropdown = page.locator('.ant-select-dropdown');
    await expect(dropdown).toBeVisible();
  });

  test('表格分页功能正常', async ({ page }) => {
    // 验证分页器存在
    const pagination = page.locator('.ant-pagination');
    await expect(pagination).toBeVisible();
  });

  test('C/D 篇切换功能正常', async ({ page }) => {
    // 点击 C篇 Tab
    await page.click('text=C篇');
    await page.waitForTimeout(500);

    // 验证 Tab 被选中
    const cTab = page.locator('.ant-tabs-tab:has-text("C篇")');
    await expect(cTab).toHaveAttribute('class', /ant-tabs-tab-active/);
  });
});
