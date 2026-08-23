/* זיהוי מוצרים בעלי שם דומה מאוד (סביר שזו אותה כפילות עם טעות הקלדה) -
 * לא מוחק/ממזג אוטומטית, רק מסמן כדי שאדם יחליט. מבוסס Levenshtein distance
 * עם סף יחסי לאורך השם, כדי לא לסמן מוצרים שונים לגמרי שרק חולקים מילה.
 */
function levenshteinDistance(a, b) {
    const m = a.length, n = b.length;
    if (m === 0) return n;
    if (n === 0) return m;
    const dp = new Array(n + 1);
    for (let j = 0; j <= n; j++) dp[j] = j;
    for (let i = 1; i <= m; i++) {
        let prevDiag = dp[0];
        dp[0] = i;
        for (let j = 1; j <= n; j++) {
            const temp = dp[j];
            dp[j] = a[i - 1] === b[j - 1]
                ? prevDiag
                : 1 + Math.min(prevDiag, dp[j], dp[j - 1]);
            prevDiag = temp;
        }
    }
    return dp[n];
}

function _duplicateThreshold(minLen) {
    if (minLen < 3) return 0;   // שמות קצרים מדי - כל שינוי הוא מהותי, לא מסמנים בכלל
    if (minLen <= 5) return 1;
    return 2;
}

/**
 * מקבל מערך שמות (מחרוזות) ומחזיר Set עם השמות שיש להם "תאום" קרוב מאוד
 * (כלומר כנראה כפילות/טעות הקלדה ולא מוצר שונה במתכוון).
 */
function findLikelyDuplicateNames(names) {
    const flagged = new Set();
    const normalized = names.map(n => (n || '').trim());
    for (let i = 0; i < normalized.length; i++) {
        for (let j = i + 1; j < normalized.length; j++) {
            const a = normalized[i], b = normalized[j];
            if (!a || !b || a === b) continue;
            const minLen = Math.min(a.length, b.length);
            const threshold = _duplicateThreshold(minLen);
            if (threshold === 0) continue;
            const dist = levenshteinDistance(a, b);
            if (dist > 0 && dist <= threshold) {
                flagged.add(a);
                flagged.add(b);
            }
        }
    }
    return flagged;
}
