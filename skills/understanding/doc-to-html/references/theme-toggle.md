# Theme toggle

每頁都帶。照抄下面的 snippet，不要另寫一套，也不要用 `prefers-color-scheme` 決定頁面顏色。Toggle 是唯一來源。

初始 `theme`（預設 `light`）只決定第一次打開時有沒有 `data-theme`；之後以 `localStorage.theme` 為準。

## 1. Head（`<title>` 之前）

```html
<meta name="color-scheme" content="light dark">
<script>try{var t=localStorage.getItem("theme");if(t==="dark")document.documentElement.setAttribute("data-theme","dark");else if(t==="light")document.documentElement.removeAttribute("data-theme")}catch(e){}</script>
```

`theme: dark` → `<html data-theme="dark">`。FOUC script 在之後的造訪覆寫。

## 2. Dark tokens

Light 用風格檔的 `:root`。Dark 一律貼這塊 Zed One Dark（含各風格會用到的別名，用不到無害）：

```css
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #282c33;
  --page: #282c33;
  --surface: #2f343e;
  --surface-elevated: #333944;
  --surface-subtle: #333944;
  --surface-hover: #333944;
  --text: #c8ccd4;
  --text-strong: #dce0e8;
  --text-muted: #838994;
  --text-faint: #5d636f;
  --border: #464b57;
  --border-strong: #555a63;
  --accent: #74ade8;
  --accent-hover: #8bbcf0;
  --accent-soft: color-mix(in srgb, #74ade8 14%, #282c33);
  --accent-contrast: #282c33;
  --success: #a1c181;
  --success-bg: color-mix(in srgb, #a1c181 12%, #282c33);
  --warning: #dec184;
  --warning-bg: color-mix(in srgb, #dec184 12%, #282c33);
  --danger: #d07277;
  --danger-bg: color-mix(in srgb, #d07277 12%, #282c33);
  --info: #74ade8;
  --info-bg: color-mix(in srgb, #74ade8 12%, #282c33);
  --code-bg: #21252b;
  --code-surface: #2f343e;
  --code-text: #c8ccd4;
  --code-muted: #838994;
  --gray-soft: #333944;
  --blue-soft: color-mix(in srgb, #74ade8 12%, #282c33);
  --green-soft: color-mix(in srgb, #a1c181 12%, #282c33);
  --yellow-soft: color-mix(in srgb, #dec184 12%, #282c33);
  --orange-soft: color-mix(in srgb, #de9e6c 12%, #282c33);
  --red-soft: color-mix(in srgb, #d07277 12%, #282c33);
  --purple-soft: color-mix(in srgb, #be95ff 12%, #282c33);
  --blue-text: #74ade8;
  --green-text: #a1c181;
  --yellow-text: #dec184;
  --red-text: #d07277;
}
```

## 3. Button

已有 topbar → 放進去，`margin-left: auto`。沒有 → 加一條只放這個 button 的 slim topbar。

```html
<button id="theme-toggle" type="button" aria-label="切換深淺色主題" title="切換深淺色主題">◐ 深/淺</button>
```

```css
#theme-toggle {
  margin-left: auto; font: inherit; font-size: 13px; line-height: 1;
  padding: 5px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm);
  background: var(--surface); color: var(--text-muted); cursor: pointer;
}
#theme-toggle:hover { color: var(--text); border-color: var(--border-strong); }
```

`@media print` 藏 `.topbar` 與 `#theme-toggle`。

## 4. Click handler（`</body>` 前）

```html
<script>
(function () {
  var root = document.documentElement;
  document.getElementById('theme-toggle').addEventListener('click', function () {
    var toDark = root.getAttribute('data-theme') !== 'dark';
    if (toDark) root.setAttribute('data-theme', 'dark'); else root.removeAttribute('data-theme');
    try { localStorage.setItem('theme', toDark ? 'dark' : 'light'); } catch (e) {}
  });
})();
</script>
```

## 5. Viz canvas

viz-it runtime（`zoompan.html`）自己跟 `data-theme` 走。頁面不要再寫一份 `.viz` 覆寫。圖用 `craft`（light）bake；不要用 `craft-dark` 當頁面主題。
