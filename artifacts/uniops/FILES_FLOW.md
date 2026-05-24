# كل الملفات الموجودة + الـ Flow بينهم

---

## أولاً — الملفات الموجودة كاملة (70 ملف)

```
artifacts/uniops/
│
├── 📄 index.html                        ← ملف HTML الوحيد (نقطة دخول المتصفح)
├── 📄 package.json                      ← كل المكتبات المستخدمة
├── 📄 vite.config.ts                    ← إعدادات سيرفر Vite
├── 📄 tsconfig.json                     ← إعدادات TypeScript
├── 📄 components.json                   ← إعدادات shadcn/ui
├── 📄 DOCUMENTATION_AR.md              ← شرح الداشبورد بالعربي
├── 📄 PROJECT_STRUCTURE.md             ← هيكل المشروع
└── 📄 FILES_FLOW.md                    ← هذا الملف
│
└── src/
    │
    ├── 📄 main.tsx                      ← [1] أول ملف يشتغل
    ├── 📄 App.tsx                       ← [2] التوجيه والروابط
    ├── 📄 index.css                     ← الثيم الداكن + كل الأنماط
    │
    ├── store/
    │   └── 📄 index.ts                  ← الحالة العامة (Zustand)
    │
    ├── lib/
    │   └── 📄 utils.ts                  ← دالة cn() لدمج CSS
    │
    ├── hooks/
    │   ├── 📄 use-mobile.tsx            ← هل الشاشة موبايل؟
    │   └── 📄 use-toast.ts             ← إشعارات Toast
    │
    ├── components/
    │   │
    │   ├── Layout/                      ← الهيكل الخارجي للتطبيق
    │   │   ├── 📄 index.tsx             ← [3] يجمع Sidebar + Header
    │   │   ├── 📄 Sidebar.tsx           ← القائمة الجانبية
    │   │   ├── 📄 Header.tsx            ← الشريط العلوي
    │   │   └── 📄 CommandPalette.tsx    ← نافذة البحث (⌘K)
    │   │
    │   └── ui/                          ← مكونات جاهزة (shadcn/ui) — 60 مكون
    │       ├── 📄 accordion.tsx         ← قوائم قابلة للطي
    │       ├── 📄 alert.tsx             ← رسائل تنبيه
    │       ├── 📄 alert-dialog.tsx      ← نافذة تأكيد
    │       ├── 📄 aspect-ratio.tsx      ← نسبة العرض للارتفاع
    │       ├── 📄 avatar.tsx            ← صورة المستخدم
    │       ├── 📄 badge.tsx             ← شارات الحالة
    │       ├── 📄 breadcrumb.tsx        ← مسار التنقل
    │       ├── 📄 button.tsx            ← الأزرار
    │       ├── 📄 button-group.tsx      ← مجموعة أزرار
    │       ├── 📄 calendar.tsx          ← تقويم
    │       ├── 📄 card.tsx              ← البطاقات
    │       ├── 📄 carousel.tsx          ← عرض شرائح
    │       ├── 📄 chart.tsx             ← مكون الرسوم البيانية
    │       ├── 📄 checkbox.tsx          ← مربع اختيار
    │       ├── 📄 collapsible.tsx       ← محتوى قابل للطي
    │       ├── 📄 command.tsx           ← قائمة بحث
    │       ├── 📄 context-menu.tsx      ← قائمة كليك يمين
    │       ├── 📄 dialog.tsx            ← نافذة منبثقة
    │       ├── 📄 drawer.tsx            ← لوح جانبي منزلق
    │       ├── 📄 dropdown-menu.tsx     ← قائمة منسدلة
    │       ├── 📄 empty.tsx             ← شاشة فارغة
    │       ├── 📄 field.tsx             ← حقل إدخال
    │       ├── 📄 form.tsx              ← نموذج
    │       ├── 📄 hover-card.tsx        ← بطاقة عند التحويم
    │       ├── 📄 input.tsx             ← حقل نص
    │       ├── 📄 input-group.tsx       ← مجموعة حقول
    │       ├── 📄 input-otp.tsx         ← حقل رمز OTP
    │       ├── 📄 item.tsx              ← عنصر قائمة
    │       ├── 📄 kbd.tsx               ← اختصار لوحة مفاتيح
    │       ├── 📄 label.tsx             ← تسمية حقل
    │       ├── 📄 menubar.tsx           ← شريط قوائم
    │       ├── 📄 navigation-menu.tsx   ← قائمة تنقل
    │       ├── 📄 pagination.tsx        ← ترقيم الصفحات
    │       ├── 📄 popover.tsx           ← نافذة صغيرة عائمة
    │       ├── 📄 progress.tsx          ← شريط تقدم
    │       ├── 📄 radio-group.tsx       ← أزرار راديو
    │       ├── 📄 resizable.tsx         ← لوحات قابلة للتمدد
    │       ├── 📄 scroll-area.tsx       ← منطقة تمرير
    │       ├── 📄 select.tsx            ← قائمة اختيار
    │       ├── 📄 separator.tsx         ← فاصل
    │       ├── 📄 sheet.tsx             ← لوح جانبي
    │       ├── 📄 sidebar.tsx           ← مكون sidebar جاهز
    │       ├── 📄 skeleton.tsx          ← تحميل وهمي
    │       ├── 📄 slider.tsx            ← شريط تمرير
    │       ├── 📄 sonner.tsx            ← إشعارات Sonner
    │       ├── 📄 spinner.tsx           ← دوامة تحميل
    │       ├── 📄 switch.tsx            ← مفتاح تبديل
    │       ├── 📄 table.tsx             ← جدول
    │       ├── 📄 tabs.tsx              ← تبويبات
    │       ├── 📄 textarea.tsx          ← حقل نص متعدد السطور
    │       ├── 📄 toast.tsx             ← إشعار عائم
    │       ├── 📄 toaster.tsx           ← حاوية الإشعارات
    │       ├── 📄 toggle.tsx            ← زر تبديل
    │       ├── 📄 toggle-group.tsx      ← مجموعة أزرار تبديل
    │       └── 📄 tooltip.tsx           ← تلميح عند التحويم
    │
    └── pages/                           ← الصفحات الـ 5
        ├── 📄 not-found.tsx             ← صفحة 404
        ├── CommandCenter/
        │   └── 📄 index.tsx             ← الصفحة الرئيسية
        ├── DevOpsCenter/
        │   └── 📄 index.tsx             ← مركز العمليات
        ├── SecurityCenter/
        │   └── 📄 index.tsx             ← مركز الأمن
        ├── CostCenter/
        │   └── 📄 index.tsx             ← مركز التكاليف
        └── MLInsights/
            └── 📄 index.tsx             ← رؤى الذكاء الاصطناعي
```

---

## ثانياً — الـ Flow (كيف تمشي البيانات)

```
المتصفح
    │
    ▼
index.html  ←─────────────────── نقطة الدخول الوحيدة
    │
    ▼
main.tsx  ←──────────────────── [1] يشغّل التطبيق ويلف كل شيء بـ BrowserRouter
    │
    ▼
App.tsx  ←───────────────────── [2] يقرأ الـ URL ويحدد أي صفحة تتعرض
    │
    ├── URL: /          ──► redirect → /command
    ├── URL: /command   ──► CommandCenter
    ├── URL: /devops    ──► DevOpsCenter
    ├── URL: /security  ──► SecurityCenter
    ├── URL: /cost      ──► CostCenter
    └── URL: /insights  ──► MLInsights
    │
    ▼
Layout/index.tsx  ←──────────── [3] يحيط الصفحة بالهيكل الخارجي
    │
    ├── Sidebar.tsx  ←────────── القائمة الجانبية (يقرأ store لحالة الطي)
    ├── Header.tsx  ←─────────── الرأس العلوي (يفتح CommandPalette)
    └── CommandPalette.tsx  ←── نافذة ⌘K (يقرأ store لحالة الفتح)
    │
    ▼
الصفحة المطلوبة  ←────────────── [4] تُعرض في المنتصف
    │
    └── تستخدم من:
        ├── components/ui/*   ← مكونات التصميم الجاهزة
        ├── recharts          ← الرسوم البيانية
        ├── framer-motion     ← الأنيميشن
        └── lucide-react      ← الأيقونات
```

---

## ثالثاً — الـ Store (إدارة الحالة)

```
store/index.ts
    │
    ├── sidebarCollapsed (true/false)
    │       │
    │       ├── يقرأه: Sidebar.tsx  ──► عشان يعرف يضغط أو يوسع
    │       └── يغيره: Sidebar.tsx  ──► عند الضغط على زر التصغير
    │
    └── commandPaletteOpen (true/false)
            │
            ├── يقرأه: CommandPalette.tsx  ──► عشان يعرف يظهر أو يخفي
            └── يغيره: Header.tsx          ──► عند الضغط على البحث أو ⌘K
```

---

## رابعاً — ملخص عدد الملفات

| المجلد | عدد الملفات | الغرض |
|--------|------------|--------|
| الجذر | 7 ملفات | إعدادات المشروع |
| `src/` | 3 ملفات | الأساس |
| `store/` | 1 ملف | الحالة العامة |
| `lib/` | 1 ملف | دوال مساعدة |
| `hooks/` | 2 ملفات | Hooks مخصصة |
| `Layout/` | 4 ملفات | الهيكل الخارجي |
| `ui/` | 60 ملف | مكونات جاهزة |
| `pages/` | 6 ملفات | الصفحات الرئيسية |
| **المجموع** | **~84 ملف** | |
