"use client";

import { useEffect, useRef } from "react";

export default function NeonSphere() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    const THREE = (window as any).THREE;
    if (!THREE) return;

    const NEON = 0x00d4ff;
    const count = 600;
    const radius = 13;
    const threshold = 2.3;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, el.clientWidth / el.clientHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);

    const group = new THREE.Group();
    const positions: any[] = [];

    const dotGeo = new THREE.SphereGeometry(0.09, 8, 8);
    const dotMat = new THREE.MeshBasicMaterial({ color: NEON, transparent: true, opacity: 0.25 });

    for (let i = 0; i < count; i++) {
      const phi = Math.acos(-1 + (2 * i) / count);
      const theta = Math.sqrt(count * Math.PI) * phi;
      const x = radius * Math.cos(theta) * Math.sin(phi);
      const y = radius * Math.sin(theta) * Math.sin(phi);
      const z = radius * Math.cos(phi);
      const v = new THREE.Vector3(x, y, z);
      positions.push(v);
      const point = new THREE.Mesh(dotGeo, dotMat);
      point.position.copy(v);
      group.add(point);
    }

    const linePts: number[] = [];
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        if (positions[i].distanceTo(positions[j]) < threshold) {
          linePts.push(positions[i].x, positions[i].y, positions[i].z);
          linePts.push(positions[j].x, positions[j].y, positions[j].z);
        }
      }
    }
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(linePts, 3));
    const lineMat = new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.10 });
    group.add(new THREE.LineSegments(lineGeo, lineMat));

    scene.add(group);
    camera.position.z = 26;

    const onResize = () => {
      if (!el) return;
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener("resize", onResize);

    let raf: number;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      group.rotation.y += 0.0015;
      group.rotation.x += 0.0004;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} className="absolute inset-0" />;
}
