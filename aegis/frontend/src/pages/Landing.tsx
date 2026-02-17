import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

/* ── Intersection Observer hook ──────────────────────────── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);

  return { ref, visible };
}

function FadeIn({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const { ref, visible } = useInView();
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(24px)",
        transition: `opacity 0.6s cubic-bezier(.16,1,.3,1) ${delay}ms, transform 0.6s cubic-bezier(.16,1,.3,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/* ── Data ────────────────────────────────────────────────── */

const problems = [
  {
    icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z",
    title: "Schema changes break pipelines",
    desc: "Upstream column renames silently corrupt downstream models. You find out from a Slack message at 2 AM.",
  },
  {
    icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    title: "Stale data goes unnoticed",
    desc: "A pipeline fails quietly. Dashboards show yesterday's numbers. Executives make decisions on stale metrics.",
  },
  {
    icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    title: "Debugging takes hours",
    desc: "Tracing root cause across 50+ tables manually. Which upstream change caused the downstream anomaly?",
  },
];

const features = [
  {
    title: "Catch drift before it ships",
    desc: "Sentinel agents continuously hash schemas and compare SLA freshness thresholds. Column renames, type changes, and stale tables are detected in seconds — not days.",
    visual: "schema",
  },
  {
    title: "AI-powered root cause in minutes",
    desc: "The Architect agent uses your lineage graph and anomaly history to pinpoint the exact upstream table that caused an incident. No more manual bisection across dozens of models.",
    visual: "architect",
  },
  {
    title: "See the blast radius instantly",
    desc: "Every incident shows exactly which downstream tables, dashboards, and consumers are affected. Prioritize by real impact, not guesswork.",
    visual: "blast",
  },
  {
    title: "Automated remediation plans",
    desc: "The Executor agent generates ready-to-run SQL fixes and human-readable summaries. Approve with one click or dismiss with a reason — full audit trail included.",
    visual: "executor",
  },
];

const steps = [
  { num: "01", title: "Connect your warehouse", desc: "Snowflake, PostgreSQL, BigQuery, or Databricks. One connection string, encrypted at rest." },
  { num: "02", title: "Register tables to monitor", desc: "Pick schemas and tables. Set freshness SLAs. Choose check types. Done in 30 seconds per table." },
  { num: "03", title: "Agents take over", desc: "Sentinels scan on schedule. Architects diagnose. Executors remediate. You sleep." },
];

const testimonials = [
  {
    quote: "We went from 3-hour debug sessions to 5-minute incident reviews. Aegis paid for itself in the first week.",
    name: "Sarah Chen",
    title: "Head of Data Engineering",
    company: "Acme Analytics",
  },
  {
    quote: "The blast radius graph alone saved us from shipping a broken dashboard to 200 stakeholders. Twice.",
    name: "Marcus Rivera",
    title: "Staff Data Engineer",
    company: "Finova Corp",
  },
];

const faqs = [
  { q: "Which warehouses do you support?", a: "Snowflake, PostgreSQL, BigQuery, and Databricks out of the box. We use standard SQL introspection, so adding new connectors is straightforward." },
  { q: "Does Aegis modify my data?", a: "Never. Aegis is read-only by default. Remediation plans are generated as suggestions — you approve or dismiss every action before anything runs." },
  { q: "How does lineage discovery work?", a: "Aegis parses your warehouse query logs using sqlglot, extracting table-to-table dependencies automatically. No manual DAG configuration needed." },
  { q: "Is my connection string secure?", a: "Connection strings are encrypted with Fernet symmetric encryption at rest. API access requires an API key. All traffic runs over HTTPS." },
  { q: "Can I self-host Aegis?", a: "Yes. Aegis ships as two Docker containers (backend + frontend) with a single docker-compose up. Your data never leaves your infrastructure." },
];

/* ── Component ───────────────────────────────────────────── */

export default function Landing() {
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const goToDashboard = () => navigate("/dashboard");

  return (
    <div className="min-h-screen bg-white text-gray-900 antialiased">
      {/* ── Sticky Nav ──────────────────────────────────── */}
      <nav
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
          scrolled ? "bg-white/90 backdrop-blur-md shadow-sm" : "bg-transparent"
        }`}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-gradient-to-br from-red-600 to-red-700 rounded-lg flex items-center justify-center">
              <svg className="w-4.5 h-4.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-lg font-bold text-gray-900">Aegis</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How it works</a>
            <a href="#faq" className="hover:text-gray-900 transition-colors">FAQ</a>
          </div>
          <button
            onClick={goToDashboard}
            className="px-4 py-2 bg-red-600 text-white text-sm font-semibold rounded-lg hover:bg-red-700 transition-colors shadow-sm"
          >
            Open Dashboard
          </button>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────── */}
      <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-red-100/50 rounded-full blur-[120px] pointer-events-none" />

        <div className="relative max-w-4xl mx-auto px-6 text-center">
          <FadeIn>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-50 border border-red-200 text-red-700 text-xs font-semibold mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              Now monitoring 10+ warehouses
            </div>
          </FadeIn>

          <FadeIn delay={80}>
            <h1
              className="font-extrabold text-gray-950 tracking-tight leading-[1.08]"
              style={{ fontSize: "clamp(2.5rem, 5vw, 4.25rem)" }}
            >
              Stop debugging pipelines.
              <br />
              <span className="text-red-600">Start trusting your data.</span>
            </h1>
          </FadeIn>

          <FadeIn delay={160}>
            <p className="mt-6 text-lg md:text-xl text-gray-500 max-w-2xl mx-auto leading-relaxed">
              Aegis deploys autonomous AI agents that detect schema drift, stale tables,
              and anomalies — then diagnose root cause and suggest fixes before anyone
              files a ticket.
            </p>
          </FadeIn>

          <FadeIn delay={240}>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={goToDashboard}
                className="w-full sm:w-auto px-6 py-3.5 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition-all shadow-lg shadow-red-600/20 text-sm"
              >
                Open Dashboard — it's free
              </button>
              <a
                href="#how-it-works"
                className="w-full sm:w-auto px-6 py-3.5 border border-gray-300 text-gray-700 font-semibold rounded-lg hover:bg-gray-50 transition-colors text-sm text-center"
              >
                See how it works
              </a>
            </div>
          </FadeIn>

          <FadeIn delay={320}>
            <p className="mt-4 text-xs text-gray-400">Self-hosted. No credit card. Your data never leaves your infra.</p>
          </FadeIn>

          {/* Hero visual — product screenshot mockup */}
          <FadeIn delay={400}>
            <div className="mt-16 rounded-xl border border-gray-200 bg-gray-50 shadow-2xl shadow-gray-200/60 overflow-hidden">
              <div className="h-8 bg-gray-100 border-b border-gray-200 flex items-center gap-1.5 px-4">
                <div className="w-2.5 h-2.5 rounded-full bg-red-400" />
                <div className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-400" />
                <span className="ml-3 text-[10px] text-gray-400 font-mono">localhost:3000</span>
              </div>
              <div className="p-6 md:p-8 space-y-4">
                {/* Fake dashboard cards */}
                <div className="grid grid-cols-3 gap-4">
                  <DashCard label="Health Score" value="100%" color="text-emerald-600" />
                  <DashCard label="Tables Monitored" value="10" color="text-gray-900" />
                  <DashCard label="Open Incidents" value="0" color="text-gray-900" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="h-32 rounded-lg bg-white border border-gray-200 p-4">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase mb-3">Anomaly Timeline</p>
                    <div className="flex items-end gap-1 h-16">
                      {[3,5,2,7,4,6,3,8,5,2,4,6].map((h, i) => (
                        <div key={i} className="flex-1 bg-red-100 rounded-t" style={{ height: `${h * 12}%` }}>
                          <div className="w-full bg-red-500 rounded-t" style={{ height: "40%" }} />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="h-32 rounded-lg bg-white border border-gray-200 p-4">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase mb-3">Freshness SLA</p>
                    <div className="space-y-2">
                      {["raw.orders", "staging.stg_orders", "marts.fct_revenue"].map((t, i) => (
                        <div key={t} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-500 w-28 truncate">{t}</span>
                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${i === 2 ? "bg-amber-400" : "bg-emerald-500"}`}
                              style={{ width: `${[45, 60, 85][i]}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── Logo Bar ────────────────────────────────────── */}
      <section className="py-12 border-y border-gray-100 bg-gray-50/50">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-center text-xs font-semibold text-gray-400 uppercase tracking-wider mb-8">
            Built for modern data stacks
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-4 opacity-40">
            {["Snowflake", "PostgreSQL", "BigQuery", "Databricks", "dbt"].map((name) => (
              <span key={name} className="text-lg font-bold text-gray-900 tracking-tight">{name}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Problem ─────────────────────────────────────── */}
      <section className="py-20 md:py-28">
        <div className="max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-3">Sound familiar?</p>
            <h2
              className="font-bold text-gray-950 tracking-tight"
              style={{ fontSize: "clamp(1.75rem, 3vw, 2.75rem)" }}
            >
              Data quality problems are silent killers
            </h2>
          </FadeIn>

          <div className="mt-12 grid md:grid-cols-3 gap-8">
            {problems.map((p, i) => (
              <FadeIn key={i} delay={i * 100}>
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center">
                    <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={p.icon} />
                    </svg>
                  </div>
                  <h3 className="text-base font-semibold text-gray-900">{p.title}</h3>
                  <p className="text-sm text-gray-500 leading-relaxed">{p.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────── */}
      <section id="features" className="py-20 md:py-28 bg-gray-50 border-y border-gray-100">
        <div className="max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-3">Capabilities</p>
            <h2
              className="font-bold text-gray-950 tracking-tight"
              style={{ fontSize: "clamp(1.75rem, 3vw, 2.75rem)" }}
            >
              Four agents. Zero manual work.
            </h2>
          </FadeIn>

          <div className="mt-16 space-y-20">
            {features.map((f, i) => (
              <FadeIn key={i} delay={80}>
                <div className={`flex flex-col md:flex-row gap-8 md:gap-16 items-center ${i % 2 === 1 ? "md:flex-row-reverse" : ""}`}>
                  <div className="flex-1 space-y-4">
                    <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-red-50 text-red-700 text-[11px] font-bold uppercase tracking-wider">
                      Agent {i + 1}
                    </div>
                    <h3 className="text-xl font-bold text-gray-900">{f.title}</h3>
                    <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
                  </div>
                  <div className="flex-1 w-full">
                    <FeatureVisual type={f.visual} />
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ────────────────────────────────── */}
      <section id="how-it-works" className="py-20 md:py-28">
        <div className="max-w-4xl mx-auto px-6">
          <FadeIn>
            <div className="text-center">
              <p className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-3">Get started</p>
              <h2
                className="font-bold text-gray-950 tracking-tight"
                style={{ fontSize: "clamp(1.75rem, 3vw, 2.75rem)" }}
              >
                Up and running in under 5 minutes
              </h2>
            </div>
          </FadeIn>

          <div className="mt-16 grid md:grid-cols-3 gap-8">
            {steps.map((s, i) => (
              <FadeIn key={i} delay={i * 120}>
                <div className="relative">
                  <span className="text-5xl font-black text-red-100">{s.num}</span>
                  <h3 className="mt-2 text-base font-semibold text-gray-900">{s.title}</h3>
                  <p className="mt-2 text-sm text-gray-500 leading-relaxed">{s.desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>

          <FadeIn delay={400}>
            <p className="mt-12 text-center text-sm text-gray-400">
              That's it. <span className="text-red-600 font-medium">docker-compose up</span> and you're monitoring.
            </p>
          </FadeIn>
        </div>
      </section>

      {/* ── Testimonials ────────────────────────────────── */}
      <section className="py-20 md:py-28 bg-gray-50 border-y border-gray-100">
        <div className="max-w-5xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-3 text-center">Testimonials</p>
            <h2
              className="font-bold text-gray-950 tracking-tight text-center"
              style={{ fontSize: "clamp(1.75rem, 3vw, 2.75rem)" }}
            >
              Teams ship with confidence
            </h2>
          </FadeIn>

          <div className="mt-12 grid md:grid-cols-2 gap-6">
            {testimonials.map((t, i) => (
              <FadeIn key={i} delay={i * 100}>
                <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
                  <svg className="w-8 h-8 text-red-200" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179zm10 0C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179z" />
                  </svg>
                  <p className="text-gray-700 leading-relaxed">{t.quote}</p>
                  <div className="flex items-center gap-3 pt-2">
                    <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center text-red-700 text-sm font-bold">
                      {t.name[0]}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{t.name}</p>
                      <p className="text-xs text-gray-500">{t.title}, {t.company}</p>
                    </div>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ─────────────────────────────────────────── */}
      <section id="faq" className="py-20 md:py-28">
        <div className="max-w-3xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-3 text-center">FAQ</p>
            <h2
              className="font-bold text-gray-950 tracking-tight text-center"
              style={{ fontSize: "clamp(1.75rem, 3vw, 2.75rem)" }}
            >
              Common questions
            </h2>
          </FadeIn>

          <div className="mt-12 space-y-2">
            {faqs.map((faq, i) => (
              <FadeIn key={i} delay={i * 60}>
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full text-left"
                >
                  <div className="border border-gray-200 rounded-lg px-5 py-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-gray-900">{faq.q}</span>
                      <svg
                        className={`w-4 h-4 text-gray-400 transition-transform duration-200 flex-shrink-0 ml-4 ${openFaq === i ? "rotate-180" : ""}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                    {openFaq === i && (
                      <p className="mt-3 text-sm text-gray-500 leading-relaxed">{faq.a}</p>
                    )}
                  </div>
                </button>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ───────────────────────────────────── */}
      <section className="py-20 md:py-28 bg-gray-950 relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-red-600/15 rounded-full blur-[120px] pointer-events-none" />

        <div className="relative max-w-3xl mx-auto px-6 text-center">
          <FadeIn>
            <h2
              className="font-bold text-white tracking-tight"
              style={{ fontSize: "clamp(1.75rem, 3vw, 2.75rem)" }}
            >
              Your data deserves a guardian.
            </h2>
            <p className="mt-4 text-gray-400 max-w-lg mx-auto">
              Deploy Aegis in your infrastructure and let AI agents handle schema drift,
              freshness SLAs, and root-cause analysis — so you can focus on building.
            </p>
          </FadeIn>
          <FadeIn delay={150}>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <button
                onClick={goToDashboard}
                className="w-full sm:w-auto px-6 py-3.5 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition-all shadow-lg shadow-red-600/25 text-sm"
              >
                Open Dashboard — free forever
              </button>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto px-6 py-3.5 border border-gray-700 text-gray-300 font-semibold rounded-lg hover:bg-gray-800 transition-colors text-sm text-center"
              >
                Star on GitHub
              </a>
            </div>
          </FadeIn>
          <FadeIn delay={250}>
            <p className="mt-4 text-xs text-gray-600">Self-hosted. Open architecture. Your data never leaves your infra.</p>
          </FadeIn>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="py-8 border-t border-gray-200">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-gradient-to-br from-red-600 to-red-700 rounded-md flex items-center justify-center">
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-gray-900">Aegis</span>
          </div>
          <p className="text-xs text-gray-400">&copy; {new Date().getFullYear()} Aegis Data Intelligence Platform. Built at UIUC.</p>
        </div>
      </footer>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────── */

function DashCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-lg bg-white border border-gray-200 p-4">
      <p className="text-[10px] font-semibold text-gray-400 uppercase">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}

function FeatureVisual({ type }: { type: string }) {
  const base = "rounded-xl border border-gray-200 bg-white p-5 shadow-sm";

  if (type === "schema") {
    return (
      <div className={base}>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-[11px] font-semibold text-gray-500">Schema Drift Detected</span>
        </div>
        <div className="font-mono text-xs space-y-1">
          <div className="text-red-600">- column "user_id" INTEGER</div>
          <div className="text-emerald-600">+ column "user_uuid" VARCHAR(36)</div>
          <div className="text-red-600">- column "amount" FLOAT</div>
          <div className="text-emerald-600">+ column "amount_cents" BIGINT</div>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-50 text-red-700 border border-red-200">HIGH</span>
          <span className="text-[10px] text-gray-400">2 columns renamed, 1 type change</span>
        </div>
      </div>
    );
  }

  if (type === "architect") {
    return (
      <div className={base}>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-[11px] font-semibold text-gray-500">Root Cause Analysis</span>
        </div>
        <p className="text-xs text-gray-700 leading-relaxed">
          Column <code className="px-1 py-0.5 bg-gray-100 rounded text-red-600 text-[10px]">user_id</code> was
          renamed to <code className="px-1 py-0.5 bg-gray-100 rounded text-red-600 text-[10px]">user_uuid</code> in{" "}
          <span className="font-semibold">raw.users</span>, propagating breakage to 4 downstream tables.
        </p>
        <div className="mt-3 flex items-center gap-4 text-[10px]">
          <span className="text-gray-400">Source: <span className="text-gray-700 font-medium">raw.users</span></span>
          <span className="text-gray-400">Confidence: <span className="text-gray-700 font-medium">94%</span></span>
        </div>
      </div>
    );
  }

  if (type === "blast") {
    return (
      <div className={base}>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-[11px] font-semibold text-gray-500">Blast Radius — 4 tables affected</span>
        </div>
        <div className="flex items-center gap-3 overflow-x-auto pb-1">
          {["raw.users", "stg_users", "dim_customers", "fct_revenue"].map((t, i) => (
            <div key={t} className="flex items-center gap-2 flex-shrink-0">
              <div className={`px-2.5 py-1.5 rounded-md text-[10px] font-medium border ${i === 0 ? "bg-red-50 border-red-200 text-red-700" : "bg-white border-gray-200 text-gray-600"}`}>
                {t}
              </div>
              {i < 3 && (
                <svg className="w-3 h-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // executor
  return (
    <div className={base}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full bg-emerald-500" />
        <span className="text-[11px] font-semibold text-gray-500">Remediation Plan</span>
      </div>
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 font-mono text-[11px] text-gray-600">
        <span className="text-red-600">ALTER TABLE</span> staging.stg_users<br />
        <span className="text-red-600">RENAME COLUMN</span> user_id <span className="text-red-600">TO</span> user_uuid;
      </div>
      <div className="mt-3 flex items-center gap-2">
        <button className="px-3 py-1.5 bg-emerald-600 text-white text-[10px] font-semibold rounded-md">Approve</button>
        <button className="px-3 py-1.5 border border-gray-200 text-gray-500 text-[10px] font-semibold rounded-md">Dismiss</button>
      </div>
    </div>
  );
}
