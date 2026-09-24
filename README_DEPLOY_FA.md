# My Control Hub V2 — نصب سریع

این نسخه برای سریع عملیاتی‌شدن طراحی شده و عمداً منوی شلوغ ندارد.

## قابلیت‌ها
- کشف خودکار همه Zoneهای فعال Cloudflare
- کارت مستقل برای هر سامانه
- Health / HTTP / Response Time
- Requests و خطاهای 5xx برای 24h / 7d / 30d
- رخدادهای فعال
- دانلود گزارش تشخیصی JSON برای ارسال به ChatGPT
- Repair Center سبک با Runbookهای فقط‌خواندنی
- بدون آرشیو سنگین: داده 30روزه هر بار از Analytics خود Cloudflare بازسازی می‌شود
- داده تولیدی در Git history ذخیره نمی‌شود؛ Pages به‌صورت Artifact Deploy می‌شود

## فقط یک‌بار انجام بده
1. محتویات این ZIP را در Repository `my-control-hub` با همین مسیرها Upload/Replace کن.
2. Secret فعلی `CLOUDFLARE_API_TOKEN` را نگه دار؛ Token جدید لازم نیست.
3. در `Settings > Pages`، Source را روی `GitHub Actions` بگذار.
4. در `Actions > My Control Hub Dashboard` روی `Run workflow` بزن.
5. بعد از سبز شدن Run، `mycontrolhub.ir` را Refresh کن.

## اضافه‌شدن سامانه‌های جدید
هر Zone جدید Cloudflare به‌صورت خودکار در پنل ظاهر می‌شود. برای نام فارسی دلخواه فقط `config/systems.json` را ویرایش کن.
