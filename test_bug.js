const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1200, height: 800 } });
  const page = await context.newPage();
  
  // Set localStorage for auth
  await page.evaluate(() => {
    localStorage.setItem('token', 'test-token-123');
    localStorage.setItem('user', JSON.stringify({ username: 'admin', display_name: '管理员' }));
    localStorage.setItem('domainPort', '8766');
  });
  
  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text().substring(0, 200)}`));
  
  const errors = [];
  page.on('pageerror', err => errors.push(err.message));
  
  // Navigate to datasources page directly
  console.log('Navigating to datasources.html...');
  await page.goto('http://localhost:8765/portal/datasources.html', { waitUntil: 'networkidle', timeout: 15000 });
  
  console.log('\n=== Console Logs ===');
  consoleLogs.forEach(l => console.log(l));
  
  console.log('\n=== Page Errors ===');
  errors.forEach(e => console.log(e));
  
  // Check page state
  const pageTitle = await page.title();
  console.log(`\nPage title: ${pageTitle}`);
  
  const btnExists = await page.$('button:has-text("新增数据源")');
  console.log(`Button exists: ${!!btnExists}`);
  
  if (btnExists) {
    const btnVisible = await btnExists.isVisible();
    console.log(`Button visible: ${btnVisible}`);
    
    // Click the button
    await btnExists.click();
    console.log('Button clicked');
    
    await page.waitForTimeout(500);
    
    // Check panel state
    const panelDisplay = await page.$eval('#panel', el => {
      const style = getComputedStyle(el);
      return { display: style.display, classList: el.className, visibility: style.visibility };
    });
    console.log(`Panel display: ${JSON.stringify(panelDisplay)}`);
    
    const overlayDisplay = await page.$eval('#overlay', el => {
      const style = getComputedStyle(el);
      return { display: style.display };
    });
    console.log(`Overlay display: ${JSON.stringify(overlayDisplay)}`);
  }
  
  // Now test via shell.html
  console.log('\n\n=== Testing via shell.html ===');
  const errors2 = [];
  page.on('pageerror', err => errors2.push(err.message));
  
  await page.goto('http://localhost:8765/portal/shell.html', { waitUntil: 'networkidle', timeout: 15000 });
  
  console.log('Shell page loaded');
  await page.waitForTimeout(1000);
  
  // Click datasources tab
  const dsTab = await page.$('.sidebar-item[data-route="datasources"]');
  if (dsTab) {
    await dsTab.click();
    console.log('Clicked datasources sidebar');
    await page.waitForTimeout(2000);
    
    // Find the iframe
    const iframe = await page.$('.tab-content iframe');
    console.log(`Iframe found: ${!!iframe}`);
    
    if (iframe) {
      const src = await iframe.getAttribute('src');
      console.log(`Iframe src: ${src}`);
      
      // Try to get iframe content frame
      try {
        // Wait for iframe to load
        await page.waitForTimeout(2000);
        
        // Access the iframe's internal page
        const frames = page.frames();
        console.log(`Total frames: ${frames.length}`);
        
        for (const frame of frames) {
          const frameUrl = frame.url();
          if (frameUrl.includes('datasources')) {
            console.log(`Found datasources frame: ${frameUrl}`);
            
            const btnInFrame = await frame.$('button:has-text("新增数据源")');
            console.log(`Button in frame exists: ${!!btnInFrame}`);
            
            if (btnInFrame) {
              const visible = await btnInFrame.isVisible();
              console.log(`Button in frame visible: ${visible}`);
              
              await btnInFrame.click();
              await page.waitForTimeout(500);
              
              const panelOpen = await frame.$eval('#panel', el => {
                const style = getComputedStyle(el);
                return { display: style.display, classList: el.className };
              });
              console.log(`Panel in frame: ${JSON.stringify(panelOpen)}`);
            }
          }
        }
      } catch (e) {
        console.log(`Iframe access error: ${e.message}`);
      }
    }
  }
  
  console.log('\n=== All Shell Errors ===');
  errors2.forEach(e => console.log(e));
  
  await browser.close();
  console.log('\nDone!');
})();