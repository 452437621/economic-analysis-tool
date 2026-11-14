<template>
<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true" focusable="false">
  <symbol id="i-grid" viewBox="0 0 24 24"><rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/></symbol>
  <symbol id="i-chart" viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M6.5 15.5l3.8-4.6 3 2.8 4.9-6.2"/><circle cx="18.2" cy="7.5" r="1.2"/></symbol>
  <symbol id="i-file" viewBox="0 0 24 24"><path d="M6 3h8l4.5 4.5V21H6z"/><path d="M14 3v5h4.5"/><path d="M9 12.5h6M9 16.5h6"/></symbol>
  <symbol id="i-palette" viewBox="0 0 24 24"><path d="M12 3a9 9 0 100 18c1.4 0 2.2-.9 2.2-2 0-1.5-1.2-1.7-1.2-3 0-1.1.9-2 2-2h1c3.3 0 5-2 5-4.5C21 6 17 3 12 3z"/><circle cx="7.6" cy="10.4" r="1"/><circle cx="10.6" cy="7.2" r="1"/><circle cx="15.4" cy="7.8" r="1"/></symbol>
  <symbol id="i-cpu" viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="2"/><path d="M10 3.5v3.5M14 3.5v3.5M10 17v3.5M14 17v3.5M3.5 10H7M3.5 14H7M17 10h3.5M17 14h3.5"/></symbol>
  <symbol id="i-activity" viewBox="0 0 24 24"><path d="M3 12h3.5l2.7-6.5 4.4 13 2.7-6.5H21"/></symbol>
  <symbol id="i-branch" viewBox="0 0 24 24"><circle cx="6" cy="5.5" r="2.2"/><circle cx="6" cy="18.5" r="2.2"/><circle cx="18" cy="12" r="2.2"/><path d="M6 7.7v8.6M8.2 5.5H12a4 4 0 014 4v.3M8.2 18.5H12a4 4 0 004-4v-.3"/></symbol>
  <symbol id="i-book" viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 016.5 3H20v18H6.5A2.5 2.5 0 014 18.5z"/><path d="M8 3v18M12 8h4M12 12h4"/></symbol>
  <symbol id="i-rates" viewBox="0 0 24 24"><path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.4"/><circle cx="17" cy="17" r="2.4"/></symbol>
  <symbol id="i-users" viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2"/><path d="M3 20.5c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 4.9a3.2 3.2 0 010 6.2"/><path d="M18.4 20.5c0-2.4-1-4.5-2.6-5.8"/></symbol>
  <symbol id="i-calendar" viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M8 3v4M16 3v4M3.5 10h17"/><path d="M8 13.5h2.5M13.5 13.5H16M8 17h2.5"/></symbol>
  <symbol id="i-bolt" viewBox="0 0 24 24"><path d="M13.5 2.5L5 13.8h5L9.5 21.5 19 10.2h-5.5z"/></symbol>
  <symbol id="i-news" viewBox="0 0 24 24"><path d="M4 5h13v15H6.5A2.5 2.5 0 014 17.5z"/><path d="M17 8h2.5A2.5 2.5 0 0122 10.5V18a2 2 0 01-2 2h-3"/><path d="M7.5 9h6M7.5 12.5h6M7.5 16h3.5"/></symbol>
  <symbol id="i-db" viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="7" ry="3.2"/><path d="M5 6v6c0 1.8 3.1 3.2 7 3.2s7-1.4 7-3.2V6"/><path d="M5 12v6c0 1.8 3.1 3.2 7 3.2s7-1.4 7-3.2v-6"/></symbol>
  <symbol id="i-shield-check" viewBox="0 0 24 24"><path d="M12 3l7.5 3v5.4c0 4.7-3.2 8.4-7.5 10.4-4.3-2-7.5-5.7-7.5-10.4V6z"/><path d="M8.7 12.1l2.2 2.2 4.4-4.6"/></symbol>
  <symbol id="i-tasks" viewBox="0 0 24 24"><path d="M9.5 6h10M9.5 12h10M9.5 18h10"/><path d="M4.5 5.6l1 1 1.6-1.8M4.5 11.6l1 1 1.6-1.8M4.5 17.6l1 1 1.6-1.8"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.2"/><path d="M15.6 15.6L20.5 20.5"/></symbol>
  <symbol id="i-bell" viewBox="0 0 24 24"><path d="M18 8.5a6 6 0 10-12 0c0 5.5-2 6.5-2 6.5h16s-2-1-2-6.5"/><path d="M10.2 19.5a2 2 0 003.6 0"/></symbol>
  <symbol id="i-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4"/></symbol>
  <symbol id="i-moon" viewBox="0 0 24 24"><path d="M20.5 14.6A8.6 8.6 0 019.4 3.5a8.6 8.6 0 1011.1 11.1z"/></symbol>
  <symbol id="i-settings" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.7 1.7 0 00-1.87-.34 1.7 1.7 0 00-1.03 1.56V21a2 2 0 11-4 0v-.08a1.7 1.7 0 00-1.11-1.56 1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-1.56-1.03H3a2 2 0 110-4h.08A1.7 1.7 0 004.6 8.86a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 112.83-2.83l.06.06A1.7 1.7 0 009 4.5h.08A1.7 1.7 0 0010.11 3V3a2 2 0 114 0v.08a1.7 1.7 0 001.03 1.56 1.7 1.7 0 001.87-.34l.06-.06a2 2 0 112.83 2.83l-.06.06A1.7 1.7 0 0019.5 9v.08a1.7 1.7 0 001.56 1.03H21a2 2 0 110 4h-.08a1.7 1.7 0 00-1.52.89z"/></symbol>
  <symbol id="i-command" viewBox="0 0 24 24"><path d="M9 6.5A2.5 2.5 0 106.5 9H18a2.5 2.5 0 10-2.5-2.5v11A2.5 2.5 0 1018 15H6.5A2.5 2.5 0 109 17.5z"/></symbol>
  <symbol id="i-close" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>
  <symbol id="i-chevron-right" viewBox="0 0 24 24"><path d="M9.5 6l6 6-6 6"/></symbol>
  <symbol id="i-chevron-left" viewBox="0 0 24 24"><path d="M14.5 6l-6 6 6 6"/></symbol>
  <symbol id="i-chevron-down" viewBox="0 0 24 24"><path d="M6 9.5l6 6 6-6"/></symbol>
  <symbol id="i-refresh" viewBox="0 0 24 24"><path d="M20 11.5a8 8 0 10-2.4 5.9"/><path d="M20 4.5v7h-7"/></symbol>
  <symbol id="i-print" viewBox="0 0 24 24"><path d="M7 9V3h10v6"/><rect x="4" y="9" width="16" height="8" rx="2"/><path d="M7 14.5h10V21H7z"/></symbol>
  <symbol id="i-download" viewBox="0 0 24 24"><path d="M12 3.5v11.5M7.5 10.5L12 15l4.5-4.5M4 20h16"/></symbol>
  <symbol id="i-copy" viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5.5 15.5V5.5A2 2 0 017.5 3.5h10"/></symbol>
  <symbol id="i-filter" viewBox="0 0 24 24"><path d="M3.5 5.5h17l-6.8 8V20l-3.4 1.5v-8z"/></symbol>
  <symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3.2 1.9"/></symbol>
  <symbol id="i-alert" viewBox="0 0 24 24"><path d="M12 3l9.5 17.5h-19z"/><path d="M12 9v5M12 17.2h.01"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24"><path d="M5 13l4.2 4L19 7.5"/></symbol>
  <symbol id="i-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8h.01"/></symbol>
  <symbol id="i-external" viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4l-8.5 8.5"/><path d="M18 13.5V19a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5.5"/></symbol>
  <symbol id="i-sort" viewBox="0 0 24 24"><path d="M8 4.5v14M5 15.5l3 3 3-3"/><path d="M16 19.5v-14M13 8.5l3-3 3 3"/></symbol>
  <symbol id="i-arrow-right" viewBox="0 0 24 24"><path d="M4 12h15M13.5 6l6 6-6 6"/></symbol>
  <symbol id="i-sparkle" viewBox="0 0 24 24"><path d="M12 3l2.1 6 6 2.1-6 2.1-2.1 6-2.1-6-6-2.1 6-2.1z"/></symbol>
  <symbol id="i-layers" viewBox="0 0 24 24"><path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/></symbol>
  <symbol id="i-pin" viewBox="0 0 24 24"><path d="M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.4"/></symbol>
  <symbol id="i-target" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.2"/><circle cx="12" cy="12" r="1"/></symbol>
  <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
  <symbol id="i-eye" viewBox="0 0 24 24"><path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/></symbol>
  <symbol id="i-flame" viewBox="0 0 24 24"><path d="M12 2.8c3.5 3.2 5.8 6.4 5.8 9.7a5.8 5.8 0 11-11.6 0c0-1.6.6-3 1.4-4.3.4 1.3 1.2 2.2 2.4 2.6-.4-3 .8-5.8 2-8z"/></symbol>
  <symbol id="i-dot-list" viewBox="0 0 24 24"><path d="M9.5 6h10M9.5 12h10M9.5 18h10"/><circle cx="4.6" cy="6" r=".9"/><circle cx="4.6" cy="12" r=".9"/><circle cx="4.6" cy="18" r=".9"/></symbol>
</svg>
</template>
