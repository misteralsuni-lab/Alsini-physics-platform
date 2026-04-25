# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: tests\worksheet-tab.spec.js >> VLE Dashboard - Worksheet Tab >> should fetch and display worksheet content successfully
- Location: tests\worksheet-tab.spec.js:4:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.fill: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('textbox', { name: 'Email Address' })

```

# Page snapshot

```yaml
- main [ref=e3]:
  - generic:
    - img
  - generic [ref=e6]:
    - link "EDU-VLE." [ref=e8] [cursor=pointer]:
      - /url: /
    - navigation [ref=e9]:
      - link "Dashboard" [ref=e10] [cursor=pointer]:
        - /url: /dashboard
      - link "My Courses" [ref=e11] [cursor=pointer]:
        - /url: /courses
      - link "Community" [ref=e12] [cursor=pointer]:
        - /url: /community
      - link "Admin" [ref=e13] [cursor=pointer]:
        - /url: /admin
    - generic [ref=e14]:
      - button "Search" [ref=e15] [cursor=pointer]:
        - img [ref=e16]
      - button "Notifications" [ref=e19] [cursor=pointer]:
        - img [ref=e20]
      - link "Login" [ref=e25] [cursor=pointer]:
        - /url: /auth
        - button "Login" [ref=e26]:
          - generic [ref=e27]: Login
  - generic [ref=e29]:
    - img "Abstract dark bioluminescence" [ref=e31]
    - generic [ref=e34]:
      - heading "PHYSICS MASTERY BEYOND limits." [level=1] [ref=e35]:
        - generic [ref=e36]: PHYSICS MASTERY BEYOND
        - generic [ref=e37]: limits.
      - paragraph [ref=e38]: EDU-VLE is a premium, open-access virtual learning environment for Edexcel IGCSE and A-Level revision.
      - generic [ref=e39]:
        - generic [ref=e40]:
          - button "Select Exam Route" [ref=e41] [cursor=pointer]:
            - generic [ref=e42]: Select Exam Route
          - button "Explore Methodology" [ref=e44] [cursor=pointer]:
            - generic [ref=e45]: Explore Methodology
          - link "Join Telegram Community" [ref=e47] [cursor=pointer]:
            - /url: https://t.me/+K6arhuYMZss2YzE0
            - generic [ref=e48]:
              - img [ref=e49]
              - text: Join Telegram Community
        - generic [ref=e52]:
          - img "EDU-VLE Telegram QR Code" [ref=e54]
          - generic [ref=e55]:
            - generic [ref=e56]: Scan to Join
            - generic [ref=e57]: Connect with the community
  - generic [ref=e59]:
    - generic [ref=e60]:
      - heading "Core Architecture" [level=2] [ref=e61]
      - heading "Interactive functional artifacts." [level=3] [ref=e62]:
        - text: Interactive functional
        - text: artifacts.
    - generic [ref=e63]:
      - generic [ref=e64]:
        - generic:
          - generic:
            - generic:
              - generic: "Topic 2: Waves & Particle Nature"
          - generic:
            - generic:
              - generic: "Topic 3: Electric Circuits"
          - generic:
            - generic:
              - generic: "Topic 1: Mechanics"
        - generic [ref=e65]:
          - heading "Structured Syllabus Mastery" [level=4] [ref=e66]
          - paragraph [ref=e67]: Content is organised into intuitive, Moodle-style collapsible topic accordions for rapid navigation and frictionless revision.
      - generic [ref=e68]:
        - generic:
          - generic:
            - generic: Live Telemetry
          - generic: "Status: OK > Initializing PhET Simulation... > Embedded Video Lesson Ready. > Past Paper DB Connected. > Awaiting Input..._"
        - generic [ref=e69]:
          - heading "Interactive Learning" [level=4] [ref=e70]
          - paragraph [ref=e71]: Seamlessly embedded video lessons, PhET simulations, and structured past paper tasks provide dynamic cognitive engagement.
      - generic [ref=e72]:
        - generic:
          - generic:
            - generic: S
            - generic: M
            - generic: T
            - generic: W
            - generic: T
            - generic: F
            - generic: S
          - generic:
            - generic: Save Protocol
          - img
        - generic [ref=e73]:
          - heading "FHEQ Level 7 Experience" [level=4] [ref=e74]
          - paragraph [ref=e75]: A highly professional, distraction-free interface explicitly optimised for iPads, designed to mimic modern university platforms.
  - generic [ref=e76]:
    - img "Bioluminescent texture" [ref=e78]
    - generic [ref=e80]:
      - paragraph [ref=e81]: "Most revision platforms focus on: fragmented content and superficial metrics."
      - paragraph [ref=e82]: "We focus on: deep mastery."
  - generic [ref=e83]:
    - generic [ref=e84]:
      - heading "Methodology" [level=2] [ref=e85]
      - heading "The Revision Protocol" [level=3] [ref=e86]
    - generic [ref=e87]:
      - generic [ref=e90]:
        - generic [ref=e91]:
          - generic [ref=e92]: 01 //
          - heading "THE FOUNDATION" [level=4] [ref=e93]
          - paragraph [ref=e94]: A rigorous grounding in Edexcel specification requirements, ensuring absolute clarity on core physical principles.
        - img [ref=e97]
      - generic [ref=e105]:
        - generic [ref=e106]: 02 //
        - heading "THE SYNTHESIS" [level=4] [ref=e107]
        - paragraph [ref=e108]: Connecting discrete concepts through interactive simulations and visual modeling to build deep tuition intuition.
      - generic [ref=e116]:
        - generic [ref=e117]:
          - generic [ref=e118]: 03 //
          - heading "THE APPLICATION" [level=4] [ref=e119]
          - paragraph [ref=e120]: Mastering exam technique with structured past paper exposure under timed conditions.
        - img [ref=e123]
  - generic [ref=e125]:
    - generic [ref=e126]:
      - heading "Commence Protocol" [level=2] [ref=e127]
      - heading "Select your exam route." [level=3] [ref=e128]
      - paragraph [ref=e129]: Begin your revision journey instantly. No login required.
    - generic [ref=e130]:
      - generic [ref=e133]:
        - heading "Level 1" [level=4] [ref=e134]
        - heading "Edexcel IGCSE" [level=5] [ref=e135]
        - list [ref=e136]:
          - listitem [ref=e137]:
            - generic [ref=e138]: ✓
            - text: Core & Extended Content
          - listitem [ref=e139]:
            - generic [ref=e140]: ✓
            - text: Interactive Quizzes
          - listitem [ref=e141]:
            - generic [ref=e142]: ✓
            - text: Full Past Paper DB
        - button "Enter IGCSE Dashboard" [ref=e143] [cursor=pointer]:
          - generic [ref=e144]: Enter IGCSE Dashboard
      - generic [ref=e148]:
        - heading "Level 2" [level=4] [ref=e149]
        - heading "Edexcel A-Level" [level=5] [ref=e150]
        - list [ref=e151]:
          - listitem [ref=e152]:
            - generic [ref=e153]: ✓
            - text: AS & A2 Modules
          - listitem [ref=e154]:
            - generic [ref=e155]: ✓
            - text: Core Practical Analysis
          - listitem [ref=e156]:
            - generic [ref=e157]: ✓
            - text: Synoptic Question Training
        - button "Enter A-Level Dashboard" [ref=e158] [cursor=pointer]:
          - generic [ref=e159]: Enter A-Level Dashboard
  - generic [ref=e162]:
    - generic [ref=e163]:
      - generic [ref=e164]:
        - generic [ref=e165]: EDU-VLE.
        - paragraph [ref=e166]: A premium, open-access virtual learning environment for Edexcel Physics revision. Designed for mastery.
        - generic [ref=e169]: System Operational
      - generic [ref=e170]:
        - heading "Navigation" [level=6] [ref=e171]
        - list [ref=e172]:
          - listitem [ref=e173]:
            - link "IGCSE Dashboard" [ref=e174] [cursor=pointer]:
              - /url: "#"
          - listitem [ref=e175]:
            - link "A-Level Dashboard" [ref=e176] [cursor=pointer]:
              - /url: "#"
          - listitem [ref=e177]:
            - link "Methodology" [ref=e178] [cursor=pointer]:
              - /url: "#syllabus"
      - generic [ref=e179]:
        - heading "Community & Legal" [level=6] [ref=e180]
        - list [ref=e181]:
          - listitem [ref=e182]:
            - link "Join Telegram" [ref=e183] [cursor=pointer]:
              - /url: https://t.me/+K6arhuYMZss2YzE0
              - img [ref=e184]
              - text: Join Telegram
          - listitem [ref=e186]:
            - link "Privacy Policy" [ref=e187] [cursor=pointer]:
              - /url: "#"
          - listitem [ref=e188]:
            - link "Terms of Service" [ref=e189] [cursor=pointer]:
              - /url: "#"
    - generic [ref=e190]:
      - paragraph [ref=e191]: © 2026 EDU-VLE. All rights reserved.
      - generic [ref=e192]: "BUILD_ID: B_7A3F9X"
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('VLE Dashboard - Worksheet Tab', () => {
  4  |   test('should fetch and display worksheet content successfully', async ({ page }) => {
  5  |     // 1. Navigate to the local server
  6  |     await page.goto('http://localhost:5173');
  7  | 
  8  |     // 2. Authenticate the user
> 9  |     await page.getByRole('textbox', { name: 'Email Address' }).fill('student@example.com'); // Replace with your test email
     |                                                                ^ Error: locator.fill: Test timeout of 30000ms exceeded.
  10 |     await page.getByRole('textbox', { name: 'Password' }).fill('your-password'); // Replace with your test password
  11 |     await page.getByRole('button', { name: 'Login' }).click();
  12 | 
  13 |     // Wait for the login to complete and navigate to the dashboard
  14 |     await page.waitForURL('**/dashboard**');
  15 | 
  16 |     // 3. Navigate to the specific chapter route (if not automatically redirected)
  17 |     await page.goto('http://localhost:5173/dashboard/unit/1/chapter/1');
  18 | 
  19 |     // 4. Wait for the InteractiveTutor component to mount
  20 |     const worksheetTab = page.locator('button', { hasText: /^Worksheet$/ }).first();
  21 |     await expect(worksheetTab).toBeVisible({ timeout: 15000 });
  22 | 
  23 |     // 5. Locate and click the 'Worksheet' tab in the UI
  24 |     const responsePromise = page.waitForResponse(response =>
  25 |       response.url().includes('supabase.co/rest/v1/resources') && response.status() === 200
  26 |     );
  27 | 
  28 |     await worksheetTab.click();
  29 |     await responsePromise;
  30 | 
  31 |     // 6. Assert that the <ReactMarkdown> container is successfully mounted and visible
  32 |     const markdownContainer = page.locator('.prose.prose-invert');
  33 |     await expect(markdownContainer).toBeVisible({ timeout: 10000 });
  34 | 
  35 |     // 7. Assert that the empty state ("No Worksheet Found") is NOT visible
  36 |     const emptyStateHeading = page.getByRole('heading', { name: 'No Worksheet Found' });
  37 |     await expect(emptyStateHeading).not.toBeVisible();
  38 |   });
  39 | });
```