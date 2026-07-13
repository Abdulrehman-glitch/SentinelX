import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '../contexts/AuthContext';
import SplitText from '../components/SplitText';

interface ScrollAnimatedHeroProps {
  brandName?: string;
  tagline?: string;
  ctaText?: string;
  onCtaClick?: () => void;
}

const ScrollAnimatedHero: React.FC<ScrollAnimatedHeroProps> = ({
  brandName = 'SentinelX',
  tagline = 'Detect. Defend. Recover.',
  ctaText = 'Log in',
  onCtaClick,
}) => {
  const navigate = useNavigate();
  const handleCta = onCtaClick ?? (() => navigate('/login'));

  const [scrollY, setScrollY] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);
  const taglineRef = useRef<HTMLParagraphElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const node = heroRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
          }
        });
      },
      { threshold: 0.1 }
    );

    if (node) {
      observer.observe(node);
    }

    return () => {
      if (node) {
        observer.unobserve(node);
      }
    };
  }, []);

  const parallaxOffset = scrollY * 0.5;
  const opacityValue = Math.max(0, 1 - scrollY / 500);

  return (
    <>
      <style>{`
        @keyframes aurora {
          0% { transform: translate(0%, 0%) rotate(0deg) scale(1); opacity: 0.6; }
          33% { transform: translate(10%, -10%) rotate(120deg) scale(1.1); opacity: 0.8; }
          66% { transform: translate(-10%, 10%) rotate(240deg) scale(0.9); opacity: 0.7; }
          100% { transform: translate(0%, 0%) rotate(360deg) scale(1); opacity: 0.6; }
        }
        @keyframes aurora-secondary {
          0% { transform: translate(0%, 0%) rotate(0deg) scale(1); opacity: 0.5; }
          33% { transform: translate(-15%, 15%) rotate(-120deg) scale(1.2); opacity: 0.7; }
          66% { transform: translate(15%, -15%) rotate(-240deg) scale(0.8); opacity: 0.6; }
          100% { transform: translate(0%, 0%) rotate(-360deg) scale(1); opacity: 0.5; }
        }
        @keyframes aurora-tertiary {
          0% { transform: translate(0%, 0%) rotate(45deg) scale(1); opacity: 0.4; }
          50% { transform: translate(20%, 20%) rotate(225deg) scale(1.15); opacity: 0.6; }
          100% { transform: translate(0%, 0%) rotate(405deg) scale(1); opacity: 0.4; }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeInScale {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
        @keyframes data-stream {
          0% { transform: translateY(-100%) translateX(0) scale(1); opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 0.8; }
          100% { transform: translateY(120vh) translateX(50px) scale(0.8); opacity: 0; }
        }
        @keyframes hex-drift {
          0% { transform: translate(0, 0) rotate(0deg); opacity: 0.4; }
          50% { transform: translate(100px, -50px) rotate(180deg); opacity: 0.7; }
          100% { transform: translate(0, 0) rotate(360deg); opacity: 0.4; }
        }
        @keyframes scan-line {
          0% { transform: translateY(-100%); }
          100% { transform: translateY(100vh); }
        }
        @keyframes grid-3d {
          0%, 100% { transform: perspective(1000px) rotateX(60deg) translateZ(0) scale(1); opacity: 0.3; }
          50% { transform: perspective(1000px) rotateX(60deg) translateZ(30px) scale(1.02); opacity: 0.6; }
        }
        @keyframes node-glow {
          0%, 100% { box-shadow: 0 0 10px rgba(200, 16, 46, 0.4), 0 0 20px rgba(200, 16, 46, 0.2); transform: scale(1); }
          50% { box-shadow: 0 0 20px rgba(200, 16, 46, 0.8), 0 0 40px rgba(200, 16, 46, 0.4); transform: scale(1.3); }
        }
        .sx-hero-tech-grid {
          position: absolute;
          inset: 0;
          background-image:
            linear-gradient(rgba(200, 16, 46, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(200, 16, 46, 0.08) 1px, transparent 1px),
            linear-gradient(rgba(200, 16, 46, 0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(200, 16, 46, 0.04) 1px, transparent 1px);
          background-size: 100px 100px, 100px 100px, 20px 20px, 20px 20px;
          animation: grid-3d 8s ease-in-out infinite;
          transform-style: preserve-3d;
        }
        .sx-hero-data-stream {
          position: absolute;
          font-family: 'JetBrains Mono', 'Courier New', monospace;
          font-size: 12px;
          font-weight: 600;
          color: rgba(200, 16, 46, 0.55);
          animation: data-stream linear infinite;
          pointer-events: none;
          text-shadow: 0 0 8px rgba(200, 16, 46, 0.45);
          letter-spacing: 2px;
          writing-mode: vertical-rl;
        }
        .sx-hero-hex {
          position: absolute;
          width: 60px;
          height: 60px;
          border: 2px solid rgba(200, 16, 46, 0.25);
          animation: hex-drift ease-in-out infinite;
          pointer-events: none;
        }
        .sx-hero-node {
          position: absolute;
          width: 8px;
          height: 8px;
          background: rgba(200, 16, 46, 0.85);
          border-radius: 50%;
          animation: node-glow 2s ease-in-out infinite;
        }
        .sx-hero-scan {
          position: absolute;
          width: 100%;
          height: 2px;
          background: linear-gradient(90deg, transparent, rgba(200, 16, 46, 0.55), transparent);
          animation: scan-line 4s linear infinite;
          box-shadow: 0 0 20px rgba(200, 16, 46, 0.7);
        }
        .sx-hero-aurora {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
        }
        .sx-hero-aurora-1 {
          width: 600px; height: 600px;
          background: radial-gradient(circle, rgba(200, 16, 46, 0.3) 0%, rgba(200, 16, 46, 0.1) 50%, transparent 100%);
          top: -200px; left: -200px;
          animation: aurora 20s ease-in-out infinite;
        }
        .sx-hero-aurora-2 {
          width: 500px; height: 500px;
          background: radial-gradient(circle, rgba(200, 16, 46, 0.25) 0%, rgba(200, 16, 46, 0.08) 50%, transparent 100%);
          bottom: -150px; right: -150px;
          animation: aurora-secondary 25s ease-in-out infinite;
        }
        .sx-hero-aurora-3 {
          width: 450px; height: 450px;
          background: radial-gradient(circle, rgba(239, 93, 110, 0.2) 0%, rgba(239, 93, 110, 0.05) 50%, transparent 100%);
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          animation: aurora-tertiary 30s ease-in-out infinite;
        }
        .sx-hero-wordmark {
          animation: fadeInScale 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          animation-delay: 0.2s;
          opacity: 0;
        }
        .sx-hero-tagline {
          animation: fadeInUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          animation-delay: 0.6s;
          opacity: 0;
        }
        .sx-hero-cta-wrap {
          animation: fadeInUp 1s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          animation-delay: 1s;
          opacity: 0;
        }
        .hover\\:shadow-xl:hover {
          box-shadow: 0 20px 25px -5px rgba(200, 16, 46, 0.12), 0 10px 10px -5px rgba(200, 16, 46, 0.06);
        }
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 20px 50px rgba(200, 16, 46, 0.4), 0 0 30px rgba(200, 16, 46, 0.3), 0 0 0 0 rgba(200, 16, 46, 0.7); }
          50% { box-shadow: 0 20px 60px rgba(200, 16, 46, 0.6), 0 0 50px rgba(200, 16, 46, 0.5), 0 0 0 10px rgba(200, 16, 46, 0); }
        }
        .sx-hero-cta {
          animation: pulse-glow 2s ease-in-out infinite;
          cursor: pointer;
        }
        .sx-hero-cta:hover { transform: scale(1.06); }
        .sx-hero-gradient-text {
          background: linear-gradient(135deg, #f2f3f5 0%, #c6c9ce 45%, #8a8e96 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        /* SplitText wraps each glyph in its own span, so the gradient has to
           be applied per character to survive the split. Brushed steel, with
           the trailing X in signal red — exactly like the wordmark. */
        .sx-hero-splitwordmark { perspective: 800px; font-family: 'Michroma', sans-serif; }
        .sx-hero-splitwordmark .split-char {
          display: inline-block;
          background: linear-gradient(180deg, #f2f3f5 0%, #c6c9ce 55%, #82868e 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
          color: transparent;
          will-change: transform, opacity;
        }
        .sx-hero-splitwordmark .split-char:last-child {
          background: linear-gradient(180deg, #ff4d5e 0%, #c8102e 60%, #8f0b20 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .sx-hero-mark {
          width: clamp(130px, 18vw, 210px);
          height: clamp(130px, 18vw, 210px);
          border-radius: 28px;
          object-fit: cover;
          box-shadow:
            0 0 0 1px rgba(255, 255, 255, 0.07),
            0 18px 60px rgba(0, 0, 0, 0.55),
            0 0 60px rgba(200, 16, 46, 0.28);
          animation: float 5s ease-in-out infinite;
        }
        .sx-hero-slogan {
          font-family: 'Michroma', sans-serif;
          letter-spacing: 0.32em;
          text-transform: uppercase;
          color: #c6c9ce;
        }
        @media (prefers-reduced-motion: reduce) {
          .sx-hero-tech-grid, .sx-hero-data-stream, .sx-hero-hex, .sx-hero-node,
          .sx-hero-scan, .sx-hero-aurora-1, .sx-hero-aurora-2, .sx-hero-aurora-3,
          .sx-hero-cta { animation: none !important; }
          .sx-hero-wordmark, .sx-hero-tagline, .sx-hero-cta-wrap {
            opacity: 1 !important; transform: none !important; animation: none !important;
          }
        }
      `}</style>

      <div
        ref={heroRef}
        className="relative min-h-screen w-full overflow-hidden bg-[#0b0d12]"
        style={{ perspective: '1000px' }}
      >
        {/* Technical Grid Background */}
        <div className="sx-hero-tech-grid" />

        {/* 3D Particles and circuit background */}
        <TechBackground scrollY={scrollY} />

        {/* Aurora Background */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="sx-hero-aurora sx-hero-aurora-1" />
          <div className="sx-hero-aurora sx-hero-aurora-2" />
          <div className="sx-hero-aurora sx-hero-aurora-3" />
        </div>

        {/* Content Container */}
        <div
          className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6"
          style={{
            transform: `translateY(${parallaxOffset}px)`,
            opacity: opacityValue,
          }}
        >
          {/* Brand mark */}
          <img
            src="/brand/sentinelx-mark.png"
            alt=""
            className="sx-hero-mark sx-hero-wordmark mb-10"
          />

          {/* Wordmark — animated letter-by-letter with GSAP SplitText */}
          <h1
            className={`mb-8 text-center text-4xl sm:text-5xl md:text-6xl lg:text-7xl ${
              isVisible ? 'visible' : ''
            }`}
          >
            <SplitText
              text={brandName}
              tag="span"
              className="sx-hero-splitwordmark"
              splitType="chars"
              delay={45}
              duration={1.1}
              ease="power3.out"
              from={{ opacity: 0, y: 60, rotateX: -90 }}
              to={{ opacity: 1, y: 0, rotateX: 0 }}
              threshold={0.15}
              rootMargin="0px"
              textAlign="center"
            />
          </h1>

          {/* Slogan */}
          <p
            ref={taglineRef}
            className="sx-hero-tagline sx-hero-slogan mb-5 max-w-3xl text-center text-sm sm:text-base md:text-lg"
          >
            {tagline}
          </p>
          <p className="sx-hero-tagline mb-16 max-w-2xl text-center text-base font-medium sm:text-lg text-[#9aa0ab]">
            Distributed Monitoring &amp; Self-Healing Platform
          </p>

          {/* CTA Button */}
          <div ref={ctaRef} className="sx-hero-cta-wrap">
            <button
              type="button"
              onClick={handleCta}
              className="sx-hero-cta rounded-full px-16 py-8 text-2xl font-bold shadow-2xl transition-all duration-300"
              style={{
                backgroundColor: '#c8102e',
                color: '#ffffff',
                boxShadow: '0 20px 50px rgba(200, 16, 46, 0.4), 0 0 30px rgba(200, 16, 46, 0.3)',
                border: '2px solid rgba(255, 255, 255, 0.3)',
              }}
            >
              {ctaText}
            </button>
          </div>
        </div>

        {/* Scroll Indicator */}
        <div
          className="absolute bottom-8 left-1/2 -translate-x-1/2 transform"
          style={{ opacity: Math.max(0, 1 - scrollY / 200) }}
        >
          <div className="flex flex-col items-center gap-2">
            <span className="text-sm font-medium tracking-wider text-[#9aa0ab]">SCROLL</span>
            <div className="h-12 w-6 rounded-full border-2 border-[#c8102e] p-1">
              <div
                className="h-2 w-2 rounded-full bg-[#c8102e]"
                style={{ animation: 'float 2s ease-in-out infinite' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Additional Content Section for Scroll Effect */}
      <div className="relative z-20 min-h-screen w-full px-6 py-24 bg-[#eff1f4]">
        <div className="mx-auto max-w-6xl">
          <h2 className="mb-12 text-center text-4xl font-bold md:text-5xl text-[#a50d24]">
            Distributed Intelligence for Every Device
          </h2>

          {/* Main intro paragraph */}
          <div className="mb-20 mx-auto max-w-3xl">
            <p className="text-center text-lg leading-relaxed md:text-xl mb-6 text-slate-600">
              SentinelX unifies laptop agents, industrial controllers and embedded IoT sensors
              into one real-time operations console. Live telemetry, configurable alert rules and
              automated recovery keep your entire fleet healthy — with strict multi-tenant isolation.
            </p>
            <p className="text-center text-lg leading-relaxed md:text-xl text-slate-600">
              Anomalies open incidents automatically, recovery actions are logged for audit, and
              role-based access keeps the right people in control — from platform admin to viewer.
            </p>
          </div>

          {/* Features Grid with Icons */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
            {/* Feature 1 */}
            <div className="flex flex-col items-center text-center p-8 rounded-2xl transition-all duration-300 hover:shadow-xl bg-[#faf0f1] backdrop-blur-sm">
              <div className="mb-6 w-20 h-20 rounded-full flex items-center justify-center bg-[#f4dfe2]">
                <svg className="w-10 h-10 text-[#a50d24]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-3 text-[#a50d24]">Real-Time Monitoring</h3>
              <p className="text-base leading-relaxed text-slate-600">
                Continuous CPU, memory, disk and embedded-sensor telemetry with instant anomaly detection across your whole fleet.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="flex flex-col items-center text-center p-8 rounded-2xl transition-all duration-300 hover:shadow-xl bg-[#faf0f1] backdrop-blur-sm">
              <div className="mb-6 w-20 h-20 rounded-full flex items-center justify-center bg-[#f4dfe2]">
                <svg className="w-10 h-10 text-[#a50d24]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-3 text-[#a50d24]">Smart Alerting</h3>
              <p className="text-base leading-relaxed text-slate-600">
                Configurable threshold rules with cooldown logic that automatically open incidents on critical events.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="flex flex-col items-center text-center p-8 rounded-2xl transition-all duration-300 hover:shadow-xl bg-[#faf0f1] backdrop-blur-sm">
              <div className="mb-6 w-20 h-20 rounded-full flex items-center justify-center bg-[#f4dfe2]">
                <svg className="w-10 h-10 text-[#a50d24]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold mb-3 text-[#a50d24]">Comprehensive Analytics</h3>
              <p className="text-base leading-relaxed text-slate-600">
                Deep insights and visualizations give your team the actionable intelligence to make informed decisions fast.
              </p>
            </div>
          </div>

          {/* Stats Section */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-20">
            <div className="text-center p-6">
              <div className="text-4xl md:text-5xl font-bold mb-2 text-[#a50d24]">99.9%</div>
              <div className="text-sm md:text-base sx-c-text0">Fleet Uptime</div>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl md:text-5xl font-bold mb-2 text-[#a50d24]">Real-time</div>
              <div className="text-sm md:text-base sx-c-text0">Telemetry</div>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl md:text-5xl font-bold mb-2 text-[#a50d24]">24/7</div>
              <div className="text-sm md:text-base sx-c-text0">Active Monitoring</div>
            </div>
            <div className="text-center p-6">
              <div className="text-4xl md:text-5xl font-bold mb-2 text-[#a50d24]">Multi-tenant</div>
              <div className="text-sm md:text-base sx-c-text0">Isolation</div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

const TechBackground: React.FC<{ scrollY: number }> = ({ scrollY }) => {
  const [dataStreams, setDataStreams] = useState<Array<{ id: number; left: string; delay: number; duration: number; data: string }>>([]);
  const [hexagons, setHexagons] = useState<Array<{ id: number; left: string; top: string; delay: number; duration: number; rotation: number }>>([]);
  const [nodes, setNodes] = useState<Array<{ id: number; left: string; top: string; delay: number }>>([]);

  useEffect(() => {
    const dataTypes = ['SECURE', 'SCAN', 'HEALTHY', 'DETECT', '0x4A2F', '0xB81C', '101010', '110011', 'ONLINE', 'VERIFY'];
    const streams = Array.from({ length: 28 }, (_, i) => ({
      id: i,
      left: `${(i * 3.4) % 100}%`,
      delay: Math.random() * 8,
      duration: 12 + Math.random() * 8,
      data: dataTypes[Math.floor(Math.random() * dataTypes.length)],
    }));
    setDataStreams(streams);

    const hexes = Array.from({ length: 16 }, (_, i) => ({
      id: i + 100,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      delay: Math.random() * 10,
      duration: 15 + Math.random() * 10,
      rotation: Math.random() * 360,
    }));
    setHexagons(hexes);

    const circuitNodes = Array.from({ length: 36 }, (_, i) => ({
      id: i + 200,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      delay: Math.random() * 3,
    }));
    setNodes(circuitNodes);
  }, []);

  const parallaxFactor = scrollY * 0.15;

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Scanning lines */}
      <div className="sx-hero-scan" style={{ animationDelay: '0s' }} />
      <div className="sx-hero-scan" style={{ animationDelay: '2s' }} />

      {/* Data streams */}
      {dataStreams.map((stream) => (
        <div
          key={stream.id}
          className="sx-hero-data-stream"
          style={{
            left: stream.left,
            animationDelay: `${stream.delay}s`,
            animationDuration: `${stream.duration}s`,
            transform: `translateY(${parallaxFactor}px)`,
          }}
        >
          {stream.data}
        </div>
      ))}

      {/* Hexagonal patterns */}
      {hexagons.map((hex) => (
        <div
          key={hex.id}
          className="sx-hero-hex"
          style={{
            left: hex.left,
            top: hex.top,
            animationDelay: `${hex.delay}s`,
            animationDuration: `${hex.duration}s`,
            transform: `rotate(${hex.rotation}deg) translateY(${parallaxFactor * 0.5}px)`,
            clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
          }}
        />
      ))}

      {/* Circuit nodes */}
      {nodes.map((node) => (
        <div
          key={node.id}
          className="sx-hero-node"
          style={{
            left: node.left,
            top: node.top,
            animationDelay: `${node.delay}s`,
            transform: `translateY(${parallaxFactor * 0.8}px)`,
          }}
        />
      ))}

      {/* SVG Circuit lines */}
      <svg className="absolute inset-0 w-full h-full" style={{ opacity: 0.3 }}>
        <defs>
          <pattern id="sx-hero-circuit" x="0" y="0" width="200" height="200" patternUnits="userSpaceOnUse">
            <path
              d="M 0 100 L 50 100 L 50 50 L 100 50 M 100 50 L 150 50 L 150 100 L 200 100 M 100 100 L 100 150 L 50 150"
              stroke="rgba(200, 16, 46, 0.4)"
              strokeWidth="2"
              fill="none"
              strokeDasharray="5,5"
            />
            <circle cx="50" cy="100" r="3" fill="rgba(200, 16, 46, 0.6)" />
            <circle cx="100" cy="50" r="3" fill="rgba(200, 16, 46, 0.6)" />
            <circle cx="150" cy="100" r="3" fill="rgba(200, 16, 46, 0.6)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#sx-hero-circuit)" />
      </svg>
    </div>
  );
};

export function LandingPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  // Already signed in? Skip the cover and go straight to the console.
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  return <ScrollAnimatedHero />;
}
