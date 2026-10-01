"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import Script from "next/script";

const NeonSphere = dynamic(() => import("@/components/NeonSphere"), { ssr: false });

/** Fixed neon-sphere background (the Scout treatment, reusable).
 * Render once per page; wrap page content in `relative z-[4]`. */
export default function AmbientBackdrop() {
  const [sphereReady, setSphereReady] = useState(false);
  return (
    <>
      <Script
        src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
        onReady={() => setSphereReady(true)}
      />
      <div className="fixed inset-0 z-[2] bg-[#0a0a0c]/82" />
      <div className="fixed inset-0 top-14 z-[3]">{sphereReady && <NeonSphere />}</div>
    </>
  );
}
