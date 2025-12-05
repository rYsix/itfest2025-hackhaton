// static/js/timezone.js
(function () {
    const cookieName = "timezone";
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

    // Если cookie уже установлена — не обновляем
    if (document.cookie.split("; ").some(row => row.startsWith(cookieName + "="))) {
        return;
    }

    // Устанавливаем cookie на 7 дней
    const expires = new Date();
    expires.setDate(expires.getDate() + 7);
    document.cookie = `${cookieName}=${encodeURIComponent(tz)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
})();
