import { test, expect } from '@playwright/test';
import path from 'path';

// Helper: create a test image using the backend API
async function createTestImage(): Promise<string> {
  const response = await fetch('http://localhost:8000/api/health');
  expect(response.ok).toBeTruthy();

  // We'll use a pre-created test image
  return '/tmp/test_document.png';
}

test.describe('Secure Translate UI Tests', () => {

  test('1. Home page loads correctly', async ({ page }) => {
    await page.goto('/');

    // Hero section
    await expect(page.locator('h1')).toContainText('Translate Documents Securely');
    await expect(page.locator('text=OCR Detection')).toBeVisible();
    await expect(page.locator('text=Multiple Engines')).toBeVisible();
    await expect(page.locator('text=Region Exclusion')).toBeVisible();

    // Upload section
    await expect(page.locator('text=Upload Document')).toBeVisible();
    await expect(page.locator('text=Click to upload')).toBeVisible();
    await expect(page.locator('text=JPG, PNG, or PDF')).toBeVisible();

    // Recent documents section
    await expect(page.locator('text=Recent Documents')).toBeVisible();

    console.log('✅ Home page loads correctly');
  });

  test('2. File upload works', async ({ page }) => {
    await page.goto('/');

    // Find the file input
    const fileInput = page.locator('input[type="file"]');

    // Upload a test image
    await fileInput.setInputFiles('/tmp/test_document.png');

    // Verify file is selected
    await expect(page.locator('text=test_document.png')).toBeVisible();
    await expect(page.locator('text=Upload Document').last()).toBeVisible();

    // Click upload button
    await page.locator('button:has-text("Upload Document")').last().click();

    // Should redirect to editor page
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Verify we're on the editor page
    await expect(page.locator('h1')).toContainText('test_document.png');
    await expect(page.locator('text=1 page')).toBeVisible();

    console.log('✅ File upload works');
  });

  test('3. Editor page loads with controls', async ({ page }) => {
    // First upload a document
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Verify editor controls
    await expect(page.locator('text=OCR Detection')).toBeVisible();
    await expect(page.locator('button:has-text("Detect Text Regions")')).toBeVisible();
    await expect(page.locator('text=Exclusion Zones')).toBeVisible();
    await expect(page.locator('button:has-text("Draw Zone")')).toBeVisible();
    await expect(page.locator('text=Languages')).toBeVisible();
    await expect(page.locator('text=Translation Engine')).toBeVisible();
    await expect(page.locator('button:has-text("Translate Document")')).toBeVisible();

    // Verify language selectors
    await expect(page.locator('text=Source')).toBeVisible();
    await expect(page.locator('text=Target')).toBeVisible();

    // Verify engine selector
    await expect(page.locator('text=Gemini')).toBeVisible();
    await expect(page.locator('text=Azure Translator')).toBeVisible();
    await expect(page.locator('text=Google Translate')).toBeVisible();

    console.log('✅ Editor page loads with controls');
  });

  test('4. OCR detection works', async ({ page }) => {
    // Upload a document first
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Click detect button
    await page.locator('button:has-text("Detect Text Regions")').click();

    // Wait for detection to complete
    await expect(page.locator('text=region')).toBeVisible({ timeout: 15000 });

    // Verify regions were detected
    const regionText = await page.locator('text=/\\d+ text region/').textContent();
    console.log(`   Detected: ${regionText}`);

    console.log('✅ OCR detection works');
  });

  test('5. Language selection works', async ({ page }) => {
    // Upload a document
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Change source language
    const sourceSelect = page.locator('select').first();
    await sourceSelect.selectOption('en');
    await expect(sourceSelect).toHaveValue('en');

    // Change target language
    const targetSelect = page.locator('select').last();
    await targetSelect.selectOption('zh-Hans');
    await expect(targetSelect).toHaveValue('zh-Hans');

    console.log('✅ Language selection works');
  });

  test('6. Engine selection works', async ({ page }) => {
    // Upload a document
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Select Azure engine
    await page.locator('input[value="azure"]').click();
    await expect(page.locator('input[value="azure"]')).toBeChecked();

    // Select Google engine
    await page.locator('input[value="google"]').click();
    await expect(page.locator('input[value="google"]')).toBeChecked();

    // Select Gemini engine
    await page.locator('input[value="gemini"]').click();
    await expect(page.locator('input[value="gemini"]')).toBeChecked();

    console.log('✅ Engine selection works');
  });

  test('7. Full translation flow', async ({ page }) => {
    // Upload a document
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Detect regions first
    await page.locator('button:has-text("Detect Text Regions")').click();
    await expect(page.locator('text=region')).toBeVisible({ timeout: 15000 });

    // Set languages
    await page.locator('select').first().selectOption('en');
    await page.locator('select').last().selectOption('zh-Hans');

    // Click translate
    await page.locator('button:has-text("Translate Document")').click();

    // Verify translation starts
    await expect(page.locator('text=Translating')).toBeVisible({ timeout: 5000 });

    // Wait for translation to complete (may take a while)
    await expect(page.locator('text=View Results')).toBeVisible({ timeout: 60000 });

    console.log('✅ Full translation flow works');
  });

  test('8. Results page loads after translation', async ({ page }) => {
    // First do a translation
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Detect and translate
    await page.locator('button:has-text("Detect Text Regions")').click();
    await expect(page.locator('text=region')).toBeVisible({ timeout: 15000 });
    await page.locator('select').first().selectOption('en');
    await page.locator('select').last().selectOption('zh-Hans');
    await page.locator('button:has-text("Translate Document")').click();
    await expect(page.locator('text=View Results')).toBeVisible({ timeout: 60000 });

    // Go to results
    await page.locator('text=View Results').click();
    await page.waitForURL(/\/results\/.*/, { timeout: 10000 });

    // Verify results page
    await expect(page.locator('text=Translation Results')).toBeVisible();
    await expect(page.locator('text=Original')).toBeVisible();
    await expect(page.locator('text=Translated')).toBeVisible();
    await expect(page.locator('button:has-text("Download Translated")')).toBeVisible();
    await expect(page.locator('button:has-text("Edit")')).toBeVisible();

    console.log('✅ Results page loads after translation');
  });

  test('9. Navigation works', async ({ page }) => {
    // Start at home
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Translate Documents Securely');

    // Upload and go to editor
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Verify we can see the document name
    await expect(page.locator('h1')).toContainText('test_document.png');

    console.log('✅ Navigation works');
  });

  test('10. Recent documents shows uploaded files', async ({ page }) => {
    // Upload a document
    await page.goto('/');
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('/tmp/test_document.png');
    await page.locator('button:has-text("Upload Document")').last().click();
    await page.waitForURL(/\/editor\/.*/, { timeout: 10000 });

    // Go back to home
    await page.goto('/');

    // Verify the document appears in recent list
    await expect(page.locator('text=test_document.png')).toBeVisible({ timeout: 5000 });

    console.log('✅ Recent documents shows uploaded files');
  });
});
