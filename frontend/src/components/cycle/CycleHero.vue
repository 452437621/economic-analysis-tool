<template>
  <!-- A. Hero：长债务周期定位 -->
  <section class="cyc-hero">
    <div class="cyc-hero-main">
      <div class="cyc-hero-eyebrow">周期定位 · 美国 / 全球长周期</div>
      <h1 class="cyc-hero-h1">{{ heroTitle }}</h1>
      <p class="cyc-hero-sub">{{ heroSub }}</p>
      <div class="cyc-hero-tags">
        <span v-for="tag in heroTags" :key="tag.key" class="cyc-tag">
          <i class="cyc-tag-dot"></i>
          <span>{{ tag.label }}</span>
          <b>{{ tag.value }}</b>
          <span v-if="tag.z !== null" class="cyc-tag-z">z {{ fmtSigned(tag.z, 1) }}</span>
        </span>
      </div>
    </div>
    <div class="cyc-hero-badges">
      <div class="cyc-meta-badge">
        <span>数据覆盖</span>
        <b>{{ coverageText }}</b>
      </div>
      <div class="cyc-meta-badge">
        <span>规则版本</span>
        <b>{{ ruleVersion }}</b>
      </div>
      <div class="cyc-meta-badge">
        <span>下次校准</span>
        <b>{{ nextCalibration }}</b>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtSigned } from "@/composables/useFormat";

interface HeroTag {
  key: string;
  label: string;
  value: string;
  z: number | null;
}

defineProps<{
  heroTitle: string;
  heroSub: string;
  heroTags: HeroTag[];
  coverageText: string;
  ruleVersion: string;
  nextCalibration: string;
}>();
</script>

<style scoped>
/* ── A. Hero ────────────────────────────────────────── */
.cyc-hero {
  position: relative;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding: 13px 16px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background:
    radial-gradient(680px 200px at 92% -40%, var(--accent-weak), transparent 70%),
    linear-gradient(115deg, color-mix(in srgb, var(--accent) 5%, transparent), transparent 52%),
    var(--surface);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 10px;
}
/* 设计稿 hero 右下角装饰圆环（纯装饰，不参与交互） */
.cyc-hero::after {
  content: "";
  position: absolute;
  right: -42px;
  bottom: -96px;
  width: 250px;
  height: 250px;
  border-radius: 50%;
  box-shadow:
    0 0 0 24px transparent,
    0 0 0 25px var(--border);
  pointer-events: none;
}
.cyc-hero-main {
  min-width: 0;
  flex: 1 1 auto;
}
.cyc-hero-eyebrow {
  font-size: 9.5px;
  letter-spacing: 1.4px;
  color: var(--dim);
  margin-bottom: 2px;
}
.cyc-hero-h1 {
  margin: 0;
  font-size: 21px;
  line-height: 1.28;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--text);
}
.cyc-hero-sub {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: var(--muted);
  line-height: 1.5;
}
.cyc-hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.cyc-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 23px;
  padding: 0 9px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  background: var(--surface-2);
  color: var(--muted);
  font-size: 10.5px;
  white-space: nowrap;
  max-width: 100%;
}
.cyc-tag b {
  font-family: var(--mono);
  font-weight: 600;
  color: var(--text);
}
.cyc-tag-z {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--dim);
}
.cyc-tag-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--warn);
  flex: none;
}
.cyc-hero-badges {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: none;
  width: 176px;
  padding-top: 3px;
}
.cyc-meta-badge {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  height: 25px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: color-mix(in srgb, var(--surface-2) 72%, transparent);
  font-size: 9.5px;
  color: var(--dim);
}
.cyc-meta-badge b {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
}

@media (max-width: 1023px) {
  .cyc-hero {
    flex-direction: column;
    gap: 10px;
  }
  .cyc-hero-badges {
    flex-direction: row;
    flex-wrap: wrap;
    width: 100%;
    padding-top: 0;
  }
  .cyc-meta-badge {
    flex: 1 1 140px;
    justify-content: space-between;
  }
}
@media (max-width: 759px) {
  .cyc-hero-h1 {
    font-size: 18px;
  }
}
</style>
