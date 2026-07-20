// ============================
// TRANSLATIONS
// ============================
// NOTE: "welcome" strings include the green-highlighted brand word
// ("Tehqeeq" / " تحقیق ") in every language, using the same
// .tehqeeq-green span, so the branding stays consistent when switching
// languages -- this was missing before (Urdu/Roman Urdu welcome text had
// no green highlight at all).
const translations = {
    en: {
        welcome: 'Welcome to <span class="tehqeeq-green">Tehqeeq</span>',
        langIndicator: '(English)',
        inputLabel: 'Enter your claim to verify:',
        placeholder: 'Paste or type your claim in English, Urdu, or Roman Urdu...',
        verifyBtn: 'Verify Claim',
        howToUseTitle: 'How to Use',
        howToUseText: 'Paste any claim or message you\'re unsure about — in English, Urdu, or Roman Urdu. Tehqeeq checks it against live web sources and gives you a clear verdict: True, False, Misleading, or Uncertain — along with the evidence behind it.',
        loadingText: 'Processing...',
        confLabel: 'Confidence',
        originalLabel: 'Original Claim',
        reasoningLabel: 'Reasoning',
        sourcesLabel: 'Sources',
        errorEmpty: 'Please enter a claim to verify.',
        errorLong: 'Claim too long (max 2000 characters).',
        true: 'TRUE',
        false: 'FALSE',
        misleading: 'MISLEADING',
        uncertain: 'UNCERTAIN',
        unknown: 'UNKNOWN',
        reasoningKey: 'english',
        rtl: false
    },
    ur: {
        welcome: '<span class="tehqeeq-green">تحقیق</span> میں خوش آمدید',
        langIndicator: '(اردو)',
        inputLabel: 'اپنا دعویٰ تحقیق کے لیے درج کریں:',
        placeholder: 'انگریزی، اردو یا رومن اردو میں اپنا دعویٰ پیسٹ یا ٹائپ کریں...',
        verifyBtn: 'تحقیق کریں',
        howToUseTitle: 'استعمال کا طریقہ',
        howToUseText: 'کوئی بھی دعویٰ یا پیغام جس پر آپ کو شک ہو، انگریزی، اردو یا رومن اردو میں یہاں لکھیں۔ تحقیق اسے تازہ ترین ذرائع سے جانچ کر آپ کو واضح جواب دے گی — سچ، جھوٹ، گمراہ کن یا غیر یقینی — اور ساتھ میں وہ ثبوت بھی جن کی بنیاد پر یہ نتیجہ اخذ کیا گیا۔',
        loadingText: 'عمل جاری ہے...',
        confLabel: 'اعتماد',
        originalLabel: 'اصل دعویٰ',
        reasoningLabel: 'استدلال',
        sourcesLabel: 'ذرائع',
        errorEmpty: 'برائے مہربانی تحقیق کے لیے دعویٰ درج کریں۔',
        errorLong: 'دعویٰ بہت طویل ہے (زیادہ سے زیادہ 2000 حروف)۔',
        true: 'سچ',
        false: 'جھوٹ',
        misleading: 'گمراہ کن',
        uncertain: 'غیر یقینی',
        unknown: 'نامعلوم',
        reasoningKey: 'urdu_script',
        rtl: true
    },
    roman: {
        welcome: '<span class="tehqeeq-green">Tehqeeq</span> mein Khush Amdeed',
        langIndicator: '(Roman Urdu)',
        inputLabel: 'Apna daawa tehqeeq ke liye darj karein:',
        placeholder: 'Angrezi, Urdu ya Roman Urdu mein apna daawa paste ya type karein...',
        verifyBtn: 'Tehqeeq Karein',
        howToUseTitle: 'Istemal ka Tareeqa',
        howToUseText: 'Koi bhi message ya daawa jis par aapko shak ho, English, Urdu, ya Roman Urdu mein yahan likhein. Tehqeeq usay live sources se check kar ke aapko saaf jawab dega — Sach, Jhoot, Gumrah Kun, ya Ghair Yaqeeni — sath hi wo saboot bhi jin ki bunyad par ye nateeja nikala gaya.',
        loadingText: 'Amal jari hai...',
        confLabel: 'Aitamad',
        originalLabel: 'Asli Daawa',
        reasoningLabel: 'Istadlaal',
        sourcesLabel: 'Zarae',
        errorEmpty: 'Baraye meharbani tehqeeq ke liye daawa darj karein.',
        errorLong: 'Daawa bohat taweel hai (zyada se zyada 2000 huroof).',
        true: 'Sach',
        false: 'Jhoot',
        misleading: 'Gumrah Kun',
        uncertain: 'Ghair Yaqeeni',
        unknown: 'Namaloom',
        reasoningKey: 'roman_urdu',
        rtl: false
    }
};

// ============================
// STATE
// ============================
let selectedLang = 'en';
let isProcessing = false;

// ============================
// DOM REFS
// ============================
const claimInput = document.getElementById('claimInput');
const charCount = document.getElementById('charCount');
const verifyBtn = document.getElementById('verifyBtn');
const verifyBtnText = document.getElementById('verifyBtnText');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');
const errorBox = document.getElementById('errorBox');
const outputSection = document.getElementById('outputSection');

const langBtns = document.querySelectorAll('.lang-btn');
const apiUrlInput = document.getElementById('apiUrlInput');

const welcomeText = document.getElementById('welcomeText');
const welcomeSentence = document.getElementById('welcomeSentence');
const langIndicator = document.getElementById('langIndicator');
const inputLabel = document.getElementById('inputLabel');
const confLabel = document.getElementById('confLabel');
const originalLabel = document.getElementById('originalLabel');
const reasoningLabel = document.getElementById('reasoningLabel');
const sourcesLabel = document.getElementById('sourcesLabel');
const sidebarHowToTitle = document.getElementById('sidebarHowToTitle');
const sidebarHowToText = document.getElementById('sidebarHowToText');

const verdictBadge = document.getElementById('verdictBadge');
const confidenceValue = document.getElementById('confidenceValue');
const confidenceFill = document.getElementById('confidenceFill');
const originalClaimWrap = document.getElementById('originalClaimWrap');
const originalClaim = document.getElementById('originalClaim');
const reasoningWrap = document.getElementById('reasoningWrap');
const reasoningText = document.getElementById('reasoningText');
const sourcesContainer = document.getElementById('sourcesContainer');
const sourcesList = document.getElementById('sourcesList');

// ============================
// LANGUAGE SWITCH
// ============================
/**
 * Switch the UI language and update all visible labels/placeholders.
 * @param {string} lang - Language key ("en" | "ur" | "roman").
 */
function switchLanguage(lang) {
    const t = translations[lang];
    if (!t) return;
    welcomeSentence.innerHTML = t.welcome;
    langIndicator.textContent = t.langIndicator;
    welcomeSentence.classList.toggle('rtl', t.rtl);

    inputLabel.textContent = t.inputLabel;
    claimInput.placeholder = t.placeholder;
    verifyBtnText.textContent = t.verifyBtn;
    sidebarHowToTitle.textContent = t.howToUseTitle;
    sidebarHowToText.textContent = t.howToUseText;
    loadingText.textContent = t.loadingText;
    confLabel.textContent = t.confLabel;
    originalLabel.textContent = t.originalLabel;
    reasoningLabel.textContent = t.reasoningLabel;
    sourcesLabel.textContent = t.sourcesLabel;

    document.body.classList.toggle('rtl-active', t.rtl);
    originalClaim.classList.toggle('rtl', t.rtl);
    reasoningText.classList.toggle('rtl', t.rtl);

    selectedLang = lang;
}

// ============================
// CHARACTER COUNTER
// ============================
// Update the on-screen character count as the user types.
claimInput.addEventListener('input', function () {
    const len = this.value.length;
    charCount.textContent = `${len} / 2000`;
});

// ============================
// LANGUAGE BUTTONS
// ============================
// Attach click handlers to language toggle buttons. When a language is
// selected we re-render any already-fetched result in the chosen language
// without calling the backend again.
langBtns.forEach(btn => {
    btn.addEventListener('click', function () {
        langBtns.forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        const lang = this.dataset.lang;
        switchLanguage(lang);

        if (outputSection.classList.contains('show') && window._lastResultData) {
            displayResult(window._lastResultData);
        }
    });
});

// ============================
// VERIFY CLAIM
// ============================
/**
 * Click handler for the "Verify" button. Validates input, calls the
 * backend `/verify` endpoint, and displays results or errors.
 */
verifyBtn.addEventListener('click', async function () {
    const claim = claimInput.value.trim();
    const t = translations[selectedLang];
    if (!claim) {
        showError(t.errorEmpty);
        return;
    }
    if (claim.length > 2000) {
        showError(t.errorLong);
        return;
    }

    hideError();
    hideOutput();
    setLoading(true);

    const apiUrl = apiUrlInput.value.trim() || 'http://localhost:8000';

    try {
        const res = await fetch(`${apiUrl}/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ claim }),
            signal: AbortSignal.timeout(90000)
        });

        const data = await res.json();

        if (res.ok && !data.is_error) {
            window._lastResultData = data;
            displayResult(data);
        } else {
            const reasoning = data.reasoning;
            const errMsg = (reasoning && typeof reasoning === 'object' ? reasoning.english : reasoning)
                || data.detail || 'Verification failed.';
            showError(errMsg);
        }
    } catch (err) {
        if (err.name === 'TimeoutError') {
            showError('Request timed out. Please try again.');
        } else if (err.name === 'AbortError') {
            showError('Request was aborted.');
        } else {
            showError('Cannot connect to API. Make sure the server is running.');
        }
    } finally {
        setLoading(false);
    }
});

// ============================
// DISPLAY RESULT
// ============================
/**
 * Render the verification `data` returned by the backend into the UI.
 * This reads pre-translated fields for multilingual display.
 * @param {object} data - Response payload from `/verify`.
 */
function displayResult(data) {
    const t = translations[selectedLang];

    // Verdict
    const verdict = (data.verdict || 'unknown').toLowerCase();
    const badgeMap = {
        'true': { class: 'true', label: t.true },
        'false': { class: 'false', label: t.false },
        'misleading': { class: 'misleading', label: t.misleading },
        'uncertain': { class: 'uncertain', label: t.uncertain }
    };
    const badge = badgeMap[verdict] || { class: 'unknown', label: t.unknown };
    verdictBadge.className = `verdict-badge ${badge.class}`;
    verdictBadge.textContent = badge.label;

    // Confidence
    let conf = data.confidence || 'low';
    let confNum = 25;
    const confLower = String(conf).toLowerCase();
    if (confLower.includes('high')) { confNum = 85; }
    else if (confLower.includes('medium')) { confNum = 50; }
    else if (confLower.includes('low')) { confNum = 25; }
    confidenceValue.textContent = `${confNum}%`;
    confidenceFill.style.width = `${confNum}%`;

    // Original claim
    originalClaim.textContent = data.original_text || claimInput.value.trim() || '';
    originalClaimWrap.style.display = 'block';

    // Reasoning -- read the pre-translated field directly from the backend.
    const reasoning = data.reasoning;
    let reasoningContent = '';
    if (reasoning && typeof reasoning === 'object') {
        reasoningContent = reasoning[t.reasoningKey] || reasoning.english || '';
    } else if (typeof reasoning === 'string') {
        // Backward-compatible fallback if the backend ever returns a plain string.
        reasoningContent = reasoning;
    }
    reasoningText.textContent = reasoningContent || 'Reasoning not available.';
    reasoningWrap.style.display = 'block';

    // Sources
    const sources = data.sources || [];
    sourcesList.innerHTML = '';
    if (sources.length > 0) {
        sourcesContainer.style.display = 'block';
        sources.forEach((src, idx) => {
            const div = document.createElement('div');
            div.className = 'source-item';

            // Pick the title in the currently selected language. The
            // snippet/content itself stays in English (that's the actual
            // evidence text from the source article) -- only the title is
            // translated, to keep this to one extra API call server-side
            // rather than translating every full snippet.
            let title = src.title || src.url || `Source ${idx + 1}`;
            if (selectedLang === 'ur' && src.title_urdu_script) {
                title = src.title_urdu_script;
            } else if (selectedLang === 'roman' && src.title_roman_urdu) {
                title = src.title_roman_urdu;
            }

            const url = src.url || '#';
            const snippet = src.content || '';
            const titleClass = selectedLang === 'ur' ? 'title rtl' : 'title';
            div.innerHTML = `
                <div style="flex:1;">
                    <div class="${titleClass}">${idx + 1}. ${title}</div>
                    ${snippet ? `<div class="snippet">${snippet}</div>` : ''}
                </div>
                <a href="${url}" target="_blank" class="source-link">View</a>
            `;
            sourcesList.appendChild(div);
        });
    } else {
        sourcesContainer.style.display = 'none';
    }

    showOutput();
}

// ============================
// UI HELPERS
// ============================
/**
 * Toggle the global loading state (disables inputs and shows overlay).
 * @param {boolean} loading
 */
function setLoading(loading) {
    isProcessing = loading;
    if (loading) {
        verifyBtn.disabled = true;
        verifyBtn.classList.add('loading');
        loadingOverlay.classList.add('show');
        hideOutput();
        hideError();
    } else {
        verifyBtn.disabled = false;
        verifyBtn.classList.remove('loading');
        loadingOverlay.classList.remove('show');
    }
}

/**
 * Reveal the output panel and scroll it into view.
 */
function showOutput() {
    outputSection.classList.add('show');
    setTimeout(() => {
        outputSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

/**
 * Hide the output panel.
 */
function hideOutput() {
    outputSection.classList.remove('show');
}

/**
 * Display an error message in the UI.
 * @param {string} msg
 */
function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.add('show');
}

/**
 * Clear any visible error message.
 */
function hideError() {
    errorBox.classList.remove('show');
    errorBox.textContent = '';
}

claimInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        verifyBtn.click();
    }
});

window._lastResultData = null;

console.log('Tasdeeq frontend loaded successfully!');