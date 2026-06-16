import WaveField from "@/components/WaveField";

// Fixed, full-viewport ambient backdrop shared by every page:
// layered red radial glows + an animated wave field + a soft vignette.
export default function WaveBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden print:hidden">
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(56rem 40rem at -2% -8%, rgba(229,62,62,0.16), transparent 58%)," +
            "radial-gradient(50rem 38rem at 102% 0%, rgba(229,62,62,0.10), transparent 55%)," +
            "radial-gradient(48rem 48rem at 90% 52%, rgba(229,62,62,0.075), transparent 60%)," +
            "radial-gradient(52rem 44rem at 4% 104%, rgba(229,62,62,0.09), transparent 60%)," +
            "radial-gradient(44rem 44rem at 60% 38%, rgba(180,30,30,0.05), transparent 62%)",
        }}
      />
      <WaveField />
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(135% 100% at 50% 28%, transparent 58%, rgba(10,10,12,0.55) 100%)",
        }}
      />
    </div>
  );
}
