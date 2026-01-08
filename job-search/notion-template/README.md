# Notion Template Import Guide

## Quick Setup (5 minutes)

### Step 1: Create a New Notion Page
1. Open Notion
2. Create a new page called **"Job Search HQ"**
3. Use the "📚 Book" or "📋 Board" icon

### Step 2: Import the Main Template
1. Open `JOB_SEARCH_HQ.md` in any text editor
2. Select all content (Cmd+A)
3. Copy (Cmd+C)
4. Paste into your Notion page (Cmd+V)
5. Notion will automatically convert the markdown!

### Step 3: Import Databases (Optional but Recommended)

For each CSV file in the `databases/` folder:

1. In Notion, type `/table` and select "Table - Full page"
2. Click "..." menu → "Merge with CSV"
3. Upload the CSV file
4. Rename the database appropriately

#### Database Files:
| File | Database Name | Purpose |
|------|---------------|---------|
| `applications.csv` | 📋 Applications | Track all job applications |
| `coding-problems.csv` | 💻 Coding Problems | 50 curated DSA problems |
| `star-stories.csv` | 🎭 STAR Stories | 20 behavioral stories |
| `lld-problems.csv` | 🔧 LLD Problems | Low-level design practice |

---

## Notion-Specific Enhancements

After importing, enhance your workspace with these Notion features:

### 1. Convert Sections to Toggle Headers
- Select any `##` header
- Type `/toggle` to convert it to a collapsible section

### 2. Add Database Views
For the Applications database, create multiple views:
- **Table View**: All applications
- **Board View**: Grouped by Stage (Kanban)
- **Calendar View**: By Next Interview Date

### 3. Create Linked Databases
Link the Applications database to multiple pages:
- Dashboard page (filtered to "Active")
- This Week's Interviews (filtered by date)
- Offers (filtered to "Offer" stage)

### 4. Add Notion Formulas

**For Applications Database - Days Since Applied:**
```
dateBetween(now(), prop("Applied Date"), "days")
```

**For Coding Problems - Progress Bar:**
```
if(prop("Status") == "Solved", "✅", "⬜")
```

### 5. Set Up Reminders
- For interview dates, add "Remind" property
- Set reminders 1 day before each interview

---

## Recommended Page Structure

```
📁 Job Search HQ
├── 📊 Dashboard (linked DBs, this week's focus)
├── 📋 Applications (full database)
├── 🏢 Companies
│   ├── Tier 1: Indian Fintech
│   ├── Tier 2: Big Tech
│   ├── Tier 3: Foreign MNCs
│   └── Tier 4: Startups
├── 📝 Resume & Profile
├── 🎭 Behavioral Prep
│   ├── STAR Stories Database
│   └── EM Philosophy
├── 💻 Technical Prep
│   ├── Coding Problems Database
│   ├── System Design Quick Refs
│   └── LLD Problems Database
├── 📚 Company Checklists
│   ├── Google
│   ├── Amazon
│   ├── Microsoft
│   └── Indian Fintech
├── 💰 Negotiation
└── 📅 Daily Log
```

---

## Database Property Types

### Applications Database
| Property | Type | Options |
|----------|------|---------|
| Company | Title | - |
| Role | Text | - |
| Tier | Select | Tier 1, 2, 3, 4 |
| Applied Date | Date | - |
| Stage | Select | Not Applied, Applied, Phone Screen, Technical, Onsite, Offer, Accepted, Rejected |
| Next Step | Text | - |
| Next Date | Date | - |
| Contact Name | Text | - |
| Contact Email | Email | - |
| Referral | Checkbox | - |
| Priority | Select | High, Medium, Low |
| Notes | Text | - |

### Coding Problems Database
| Property | Type | Options |
|----------|------|---------|
| Problem | Title | - |
| Pattern | Select | Arrays, Two Pointers, Sliding Window, etc. |
| Difficulty | Select | Easy, Medium, Hard |
| Status | Select | Not Started, In Progress, Solved, Review |
| LeetCode Link | URL | - |
| Notes | Text | - |
| Last Practiced | Date | - |

### STAR Stories Database
| Property | Type | Options |
|----------|------|---------|
| Title | Title | - |
| Primary Theme | Select | Conflict, Hiring, Failure, etc. |
| Amazon LP | Select | All 16 LPs |
| Status | Select | Not Written, Draft, Polished |
| Situation | Text | - |
| Task | Text | - |
| Action | Text | - |
| Result | Text | - |
| Learning | Text | - |

---

## Tips for Best Experience

### 1. Use Templates
Create Notion templates for:
- Daily log entries
- Company research notes
- Interview debrief

### 2. Set Up Synced Blocks
Use synced blocks for:
- Your key metrics (appear on multiple pages)
- Weekly goals (dashboard + daily log)

### 3. Use Notion AI (if available)
- Summarize company research
- Help write STAR stories
- Generate interview questions

### 4. Mobile App
- Install Notion mobile app
- Quick-add applications on the go
- Review STAR stories before interviews

---

## Backup Your Progress

Notion auto-saves, but periodically:
1. Export workspace as Markdown
2. Keep your CSVs updated
3. Screenshot your Kanban board for progress tracking

---

## Need Help?

- [Notion Help Center](https://www.notion.so/help)
- [Notion Templates Gallery](https://www.notion.so/templates)
- [r/Notion](https://www.reddit.com/r/Notion/)

Good luck with your job search! 🚀

