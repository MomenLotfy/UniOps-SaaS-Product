# هيكل مشروع UniOps Control Tower

```
artifacts/uniops/
│
├── src/
│   │
│   ├── main.tsx                        ← نقطة الدخول الرئيسية للتطبيق (BrowserRouter)
│   ├── App.tsx                         ← التوجيه الرئيسي (Routes) + تحميل الصفحات
│   ├── index.css                       ← كل الأنماط والثيم الداكن (CSS Variables)
│   │
│   ├── store/
│   │   └── index.ts                    ← الحالة العامة للتطبيق (Zustand)
│   │                                      • sidebarCollapsed (مطوية/مفتوحة)
│   │                                      • commandPaletteOpen (مفتوحة/مغلقة)
│   │                                      • toggleSidebar / setCommandPalette
│   │
│   ├── components/
│   │   │
│   │   ├── Layout/
│   │   │   ├── index.tsx               ← الهيكل الرئيسي (Sidebar + Header + محتوى)
│   │   │   ├── Sidebar.tsx             ← القائمة الجانبية (5 روابط + أنيميشن)
│   │   │   ├── Header.tsx              ← الرأس (بحث + إشعارات + مستخدم)
│   │   │   └── CommandPalette.tsx      ← نافذة البحث السريع (⌘K)
│   │   │
│   │   └── ui/                         ← مكونات shadcn/ui الجاهزة (60+ مكون)
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── badge.tsx
│   │       ├── table.tsx
│   │       ├── tabs.tsx
│   │       ├── chart.tsx
│   │       ├── dialog.tsx
│   │       ├── dropdown-menu.tsx
│   │       └── ...
│   │
│   ├── pages/
│   │   │
│   │   ├── CommandCenter/
│   │   │   └── index.tsx               ← الصفحة الرئيسية
│   │   │                                  • Summary Cards (4 بطاقات)
│   │   │                                  • Area Chart (CPU + Memory 24h)
│   │   │                                  • Pie Chart (Service Health)
│   │   │                                  • Service Status List
│   │   │                                  • Recent Events Feed
│   │   │
│   │   ├── DevOpsCenter/
│   │   │   └── index.tsx               ← مركز العمليات
│   │   │                                  • Tab: Overview (Resource Chart)
│   │   │                                  • Tab: Pipelines (جدول CI/CD)
│   │   │                                  • Tab: Kubernetes (جدول Pods)
│   │   │                                  • Tab: History (سجل النشر)
│   │   │
│   │   ├── SecurityCenter/
│   │   │   └── index.tsx               ← مركز الأمن
│   │   │                                  • Tab: Overview (Radar + Trend)
│   │   │                                  • Tab: Active Threats (بطاقات التهديدات)
│   │   │                                  • Tab: Vulnerabilities (جدول CVEs)
│   │   │                                  • Tab: Compliance (أطر الامتثال)
│   │   │
│   │   ├── CostCenter/
│   │   │   └── index.tsx               ← مركز التكاليف
│   │   │                                  • Tab: Overview (Budget + Pie)
│   │   │                                  • Tab: By Service (جدول الخدمات)
│   │   │                                  • Tab: Forecast (تنبؤ 30 يوم)
│   │   │                                  • Tab: Savings (فرص التوفير + شذوذات)
│   │   │
│   │   ├── MLInsights/
│   │   │   └── index.tsx               ← رؤى الذكاء الاصطناعي
│   │   │                                  • Tab: Correlations (Scatter + Radar)
│   │   │                                  • Tab: Predictions (LSTM 48h)
│   │   │                                  • Tab: Patterns (بطاقات الأنماط)
│   │   │                                  • Tab: Recommendations (التوصيات)
│   │   │
│   │   └── not-found.tsx               ← صفحة 404
│   │
│   ├── hooks/
│   │   ├── use-mobile.tsx              ← Hook لاكتشاف الشاشات الصغيرة
│   │   └── use-toast.ts               ← Hook للإشعارات (Toast)
│   │
│   └── lib/
│       └── utils.ts                    ← دوال مساعدة (cn لدمج CSS classes)
│
├── index.html                          ← ملف HTML الرئيسي
├── vite.config.ts                      ← إعدادات Vite (منفذ + مسار التطبيق)
├── tsconfig.json                       ← إعدادات TypeScript
├── package.json                        ← المكتبات المستخدمة
├── DOCUMENTATION_AR.md                 ← شرح تفصيلي بالعربي
└── PROJECT_STRUCTURE.md                ← هذا الملف
```

---

## المكتبات الأساسية المستخدمة

| المكتبة | الغرض |
|---------|--------|
| `react` + `typescript` | الأساس |
| `react-router-dom` | التنقل بين الصفحات |
| `zustand` | إدارة الحالة العامة |
| `framer-motion` | الأنيميشن والحركات |
| `recharts` | الرسوم البيانية |
| `lucide-react` | الأيقونات |
| `clsx` | دمج CSS classes بشكل شرطي |
| `tailwindcss v4` | الثيم والتنسيق |

---

## قاعدة التصميم

```
كل صفحة (page) تحتوي على:
├── بطاقات ملخص (Summary Cards)    ← أرقام سريعة في الأعلى
├── تبويبات (Tabs)                  ← للتنقل بين العروض
└── محتوى التبويب                   ← جداول + رسوم بيانية + بطاقات
```
