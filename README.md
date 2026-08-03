# Growth Portal

مكان واحد بيقرا من كل المصادر، بيطلع حكم لكل كيان، وكل حكم معاه دليله. وفوق ده
طبقة agent بتحقق وتبعت تنبيهات.

## ليه مبني كده

كل قاعدة في المشروع ده متكتبة بسبب استنتاج غلط حصل فعلاً وهو بيتحلل بالإيد:

| القاعدة | الغلط اللي منعها |
|---|---|
| مقام من نفس المصدر إجباري | مقارنة تحويلات جوجل (٤) بإجمالي أوردرات ERPNext (٣١٠) — ده حصة سوقية مش أداء |
| `assert_mature` قبل أي حكم | الحكم على يوم لسه بيتحرك: ERPNext بيعمل backfill، PMAX بيتأخر ٧٢ ساعة |
| `impact_floor` جنب نسبة الفجوة | فجوة ٦.٦ نقطة على حجم كبير بتكلّف ٤ أضعاف فجوة ١٠.٧ على منتج صغير — البوابة على النسبة لوحدها بتبلّغ عن الصغير وتسكت عن الكبير |
| `min_weight` | منتج تغليف بـ١٠١ أوردر و٥٤ درهم كان هياخد حكم Grow على نسبة تسليمه |
| الحكم على الأوردرات المحسومة بس | القسمة على الأوردرات الموضوعة بتخلي كل منتج جديد شكله فاشل |
| `Watch` بصوت عالي | العينة الصغيرة لازم تتقال، لأن السكوت بيتقري «مفيش مشكلة» |
| نفس البوابة المالية على Grow | أقوى مرشح للتوسّع كان بيختفي بينما منتج أصغر بياخد حكم |

## الطبقات

```
sources/     ← بتسحب بس. مفيش نسب هنا.
engine/      ← guard.py بيرفض الأطر الغلط · verdict.py بيحكم ويرتّب بالفلوس
analyzers/   ← منطق كل نوع كيان، بيسلّم للمحرك ومش بيكتب حكم بنفسه
agent/       ← بيقرا الاتنين، بيحقق، بيكتب Growth Finding
notify/      ← ميل دايماً · واتساب للـ Critical/High بس
api/         ← endpoints للواجهة
frontend/    ← Vue 3 + Vite، RTL
```

الـ agent **مش** بينفذ. مفيش عنده أداة كتابة على أي منصة إعلانية — بيكتب نتيجة
وبيبعت تنبيه، والتنفيذ قرار بشري.

## التشغيل

### الواجهة على اللوكال (داتا عيّنة من تشغيل حقيقي)

```bash
npm --prefix /Users/ahmedbadran/Growth/growth-portal/frontend run dev
```

`http://localhost:8770` — من غير bench بترجع داتا العيّنة مع بانر واضح إن دي مش حيّة.
نفس الـ design system بتاع Task Hub (Tailwind + ink/brand + Inter/Noto Sans Arabic)
عشان البورتالين يبانوا منتج واحد. الألوان الزيادة الوحيدة هي ألوان الأحكام —
دي بتحمل معنى، فمبتتخلطش مع لون البراند.

الـ build بيطلع bundle واحد لـ `growth_portal/public/` لأن الـ Jinja shell
بيسمّي ملفين ثابتين:

```bash
npm --prefix /Users/ahmedbadran/Growth/growth-portal/frontend run build
```

### على السيرفر

```bash
bench get-app growth_portal /path/to/growth-portal && bench --site <site> install-app growth_portal
```

في `site_config.json`:

```json
{
  "anthropic_api_key": "sk-ant-…",
  "growth_alert_email": "ahmedbadran2017@gmail.com",
  "growth_alert_whatsapp_webhook": "https://n8n…/webhook/growth-alert",
  "growth_alert_whatsapp_to": "+90…"
}
```

بعدين backfill مرة واحدة، وإلا أول تشغيل هيطلع Watch على كل حاجة لعدم وجود خط أساس:

```bash
bench --site <site> execute growth_portal.install.backfill --kwargs '{"days": 90}'
```

الجدولة: sync كل ساعة، والحكم + الـ agent الساعة ٩ صباحاً بعد ما اليوم يستوي.

## الحالة

| الجزء | الحالة |
|---|---|
| `sources/erpnext.py` | كامل — ٠ حالة courier غير معروفة على ١٠٠٠ صف حقيقي |
| `analyzers/product.py` | كامل — اتشغّل على ٧٩ منتج، طلّع حكم واحد بأثر ٨٬٨٢٧ درهم/شهر |
| `engine/` | كامل ومتفحص على داتا حقيقية |
| `agent/` | كامل — ٦ أدوات، كلها قراءة ما عدا كتابة النتايج |
| باقي المصادر السبعة | contracts مكتوبة، التنفيذ لسه |
| باقي المحللين الستة | نفس الحال |

المصدر بيتسجّل في `SOURCES` في `tasks.py` بس لما يرجع صفوف فعلاً — مصدر مسجّل
وهو stub بيخلي شريط السلامة يكدب باللون الأخضر.
