// Same shape as Task Hub's: t() maps the English source string to the active
// locale, so keys ARE the English strings and untranslated text degrades to
// English rather than to a missing-key placeholder.
//
// Default is English. Arabic flips the document to RTL.
//
// Note what is NOT translated here: verdict headlines, recommended actions and
// agent findings are generated server-side and stored, so they arrive in one
// language and stay in it. They are written in English for the same reason the
// interface defaults to English.
import { ref } from "vue";

const AR = {
  // chrome
  "Growth Portal": "بورتال النمو",
  Verdicts: "الأحكام",
  Findings: "نتائج التحقيق",
  "Measurement Integrity": "سلامة القياس",
  Integrity: "القياس",
  "Ask the analyst": "اسأل المحلل",
  Ask: "اسأل",
  Connections: "الاتصالات",
  Settings: "الإعدادات",
  System: "النظام",
  Refresh: "تحديث",
  Language: "اللغة",
  "Open impact": "إجمالي الأثر المفتوح",
  "MAD/mo": "درهم/شهر",
  "All sources live": "كل المصادر حيّة",
  "{0} problems": "{0} مشكلة",

  // sample-data banner
  "Your account does not have access to the Growth Portal — ask an admin for the Growth Portal Analyst role.":
    "حسابك مش معاه صلاحية على بورتال النمو — اطلب من الأدمن دور Growth Portal Analyst.",
  "The server answered with an error ({0}). What you see below is sample data, not your numbers.":
    "السيرفر رجّع خطأ ({0}). اللي تحت داتا عيّنة، مش أرقامك.",
  "No connection to the server — this is sample data from a real engine run (6 Jul – 2 Aug 2026). Action buttons are disabled.":
    "مفيش اتصال بالسيرفر — اللي ظاهر داتا عيّنة من تشغيل المحرك على أرقام حقيقية (٦ يوليو – ٢ أغسطس ٢٠٢٦). أزرار التنفيذ متعطّلة.",

  Overview: "نظرة عامة",
  Capacity: "السعة",
  Campaign: "الكامبين",
  Utilization: "الاستخدام",
  "Spend/day": "صرف/يوم",
  Budget: "البدجت",
  Constraint: "القيد",
  "Budget-capped": "مسقوف بالبدجت",
  "Delivery-limited": "محدود بالتسليم",
  Normal: "عادي",
  Unknown: "غير معروف",
  "of authorised budget used": "من البدجت المصرّح مستخدم",
  of: "من",
  "no budget data": "مفيش بيانات بدجت",
  "budget-capped above here": "مسقوف بالبدجت فوق كده",
  "No campaign spend in this window": "مفيش صرف كامبينات في المدى ده",
  "{0} campaign(s) have no budget data — their capacity is unknown, not unlimited.":
    "{0} كامبين من غير بيانات بدجت — سعتهم غير معروفة، مش غير محدودة.",
  Today: "النهاردة",
  "This month": "الشهر ده",
  Orders: "الأوردرات",
  Sales: "المبيعات",
  "Ad spend": "صرف الإعلانات",
  Confirmation: "التأكيد",
  Confirmed: "مؤكد",
  Delivered: "مُسلَّم",
  "Confirmation rate": "نسبة التأكيد",
  "Delivery rate": "نسبة التسليم",
  "call centre · confirmed ÷ all orders placed": "الكول سنتر · المؤكد ÷ كل الأوردرات",
  "courier · delivered ÷ resolved orders": "شركة الشحن · المسلَّم ÷ الأوردرات المحسومة",
  "still in transit": "لسه في الطريق",
  "Ad spend, all platforms": "صرف الإعلانات، كل المنصات",
  "No TRY→MAD rate configured — spend is not comparable to sales above":
    "مفيش سعر تحويل ليرة←درهم — الصرف مش قابل للمقارنة بالمبيعات فوق",
  "No platform has reported spend yet — the adapters are written but have never run.":
    "مفيش منصة بلّغت صرف لسه — الـ adapters مكتوبة بس ما اشتغلتش.",
  "Blended cost / order": "تكلفة مخلوطة / أوردر",
  "Blended cost / delivered": "تكلفة مخلوطة / مُسلَّم",
  "spend ÷ all orders, across every platform — not attributed":
    "الصرف ÷ كل الأوردرات على كل المنصات — مش منسوب",
  "Suppliers & Products": "الموردين والمنتجات",
  Segments: "التقسيمات",
  Suppliers: "الموردين",
  Products: "المنتجات",
  Supplier: "المورد",
  Product: "المنتج",
  Share: "الحصة",
  Revenue: "الإيراد",
  SKUs: "أصناف",
  Confirm: "تأكيد",
  Delivery: "تسليم",
  "filtered to": "مفلتر على",
  "last {0} days": "آخر {0} يوم",
  "No rows in this window": "مفيش صفوف في المدى ده",
  "Share is of the rows listed. Confirmation is the call centre; delivery is the courier — different systems, different denominators.":
    "الحصة من الصفوف المعروضة. التأكيد من الكول سنتر والتسليم من شركة الشحن — نظامين مختلفين ومقامين مختلفين.",
  "Media Buyers": "الميديا بايرز",
  Buyers: "البايرز",
  Performance: "الأداء",
  Activity: "النشاط",
  Spend: "الصرف",
  campaigns: "كامبين",
  "platform ROAS": "ROAS المنصة",
  "No platform spend in the window yet": "مفيش صرف منصات في المدى لسه",
  "No change log entries yet — platform audit logs arrive with the first sync":
    "مفيش سجل تغييرات لسه — سجلات المنصات بتيجي مع أول مزامنة",
  "active days": "يوم نشط",
  last: "آخر",
  "by them": "منهم",
  automation: "أتمتة",
  "Change-log coverage:": "تغطية سجل التغييرات:",
  "without a surface": "من غير مصدر",
  "{0} account(s) are not mapped to a buyer — their spend shows as Unassigned.":
    "{0} حساب مش مربوط ببايَر — صرفه بيظهر Unassigned.",
  "Platform-reported ROAS, per platform. Buyers run different accounts and products — this is not a ranking.":
    "ROAS بحساب المنصة، لكل منصة. البايرز بيشغّلوا حسابات ومنتجات مختلفة — ده مش ترتيب.",

  // verdicts
  All: "الكل",
  Grow: "فرصة نمو",
  Fix: "محتاج إصلاح",
  Kill: "أوقفه",
  Dormant: "واقف",
  Watch: "تحت الملاحظة",
  "Above baseline — the same spend buys a better result": "أعلى من المتوسط — نفس الصرف بيجيب نتيجة أحسن",
  "Below baseline by a costly margin": "تحت المتوسط بفجوة مكلّفة",
  "Below the point of viability": "تحت حد الجدوى",
  "No activity for a while": "مفيش شغل عليه من فترة",
  "Sample too small for a verdict": "العيّنة أصغر من إن الحكم يتقال",
  "No estimated impact": "مفيش أثر مقدّر",
  baseline: "متوسط",
  "Largest failure source": "أكبر مصدر فشل",
  "Numerator ÷ denominator": "البسط ÷ المقام",
  "Denominator source": "مصدر المقام",
  Window: "النافذة",
  Sample: "العيّنة",
  Query: "الاستعلام",
  "Revenue ÷ spend": "الإيراد ÷ الصرف",
  "Cost per purchase": "تكلفة الشرائية",
  Currency: "العملة",
  "days still maturing — this is a floor, not a final number":
    "يوم لسه بيتحرك — الرقم ده حد أدنى مش نهائي",
  "not enough history": "مفيش تاريخ كفاية",
  Acknowledge: "شفتها",
  Actioned: "نفّذت",
  Dismiss: "مش صح",
  "No verdicts here": "مفيش حكم هنا",
  "If the sources above are live, this means no gap cleared the threshold — not that nothing was checked.":
    "لو المصادر حيّة، ده معناه إن مفيش فجوة عدّت الحد — مش إن مفيش فحص.",

  // failure owners
  "Product page": "صفحة المنتج",
  "Lead quality": "جودة الليدز",
  Confirmation: "التأكيد",
  "Duplicate orders": "أوردرات مكرّرة",
  Logistics: "الشحن",
  Customer: "العميل",
  Unreachable: "تعذّر وصول",
  "Product refused": "رفض منتج",
  Duplicate: "مكرّر",

  // integrity
  Sources: "المصادر",
  Live: "حيّ",
  Down: "واقف",
  rows: "صف",
  "Ratios off their baseline": "نسب خرجت عن خط أساسها",
  Value: "القيمة",
  Baseline: "خط الأساس",
  "Latest day with data": "آخر يوم فيه داتا",
  "A source or a ratio needs a look": "في مصدر أو نسبة محتاجة نظرة",
  "A source silently returning zero rows looks identical to one reporting real zeros. The first is a broken token, the second an emergency — this screen is what tells them apart.":
    "مصدر بيرجع صفر صفوف في صمت شكله زي مصدر بيبلّغ عن أصفار حقيقية. الأول توكن باظ، والتاني طوارئ — والشاشة دي هي اللي بتفرّق بينهم.",

  // findings
  Critical: "حرج",
  High: "عالي",
  Medium: "متوسط",
  Low: "منخفض",
  "No open findings": "مفيش نتايج مفتوحة",
  "The analyst runs at 09:00, after the day is mature enough to judge.":
    "المحلل بيشتغل الساعة ٩ صباحاً بعد ما اليوم يستوي.",
  Numerator: "البسط",
  Denominator: "المقام",
  From: "من",
  To: "لـ",

  // ask
  "Reads, investigates and recommends — it does not execute on any platform":
    "بيقرا ويحقق ويوصّي — مبينفّذش على أي منصة",
  "e.g. why did the delivery rate drop this week?": "مثلاً: ليه نسبة التسليم نزلت الأسبوع ده؟",
  "Investigating…": "بيحقق…",
  "Needs a server connection": "محتاج اتصال بالسيرفر",
  "tool calls": "استدعاء أداة",
  "Which product is losing the most money right now?": "أنهي منتج بيخسر أكتر فلوس دلوقتي؟",
  "Did any ratio drift off its baseline this week?": "في نسبة خرجت عن خط أساسها الأسبوع ده؟",
  "What changed before the delivery rate fell?": "إيه اللي اتغيّر قبل ما التسليم ينزل؟",
};

const DICTS = { ar: AR };

export const LOCALES = [
  { code: "en", label: "EN", name: "English" },
  { code: "ar", label: "ع", name: "العربية" },
];

const KNOWN = ["en", "ar"];

function normalize(l) {
  l = String(l || "").toLowerCase().slice(0, 2);
  return KNOWN.includes(l) ? l : "en";
}

function initialLocale() {
  const saved = localStorage.getItem("gp_lang");
  if (saved && KNOWN.includes(saved)) return saved;
  // No explicit choice yet. Unlike Task Hub this does NOT follow the user's
  // ERPNext language: the numbers, the query references and the agent's own
  // findings are all in English, so an Arabic default would produce a page
  // that is half-translated by construction.
  return "en";
}

const locale = ref(initialLocale());
applyDir();

function applyDir() {
  if (typeof document !== "undefined") {
    document.documentElement.dir = locale.value === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = locale.value;
  }
}

export function useI18n() {
  function t(s, ...args) {
    const dict = DICTS[locale.value];
    let out = (dict && dict[s]) || s;
    args.forEach((a, i) => (out = out.replace(`{${i}}`, a)));
    return out;
  }
  function setLocale(l) {
    locale.value = l;
    localStorage.setItem("gp_lang", l);
    applyDir();
  }
  return { t, locale, setLocale, LOCALES };
}
