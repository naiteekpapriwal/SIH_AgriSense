'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Activity, Microscope, Bell } from 'lucide-react';

const navItems = [
  { href: '/', icon: LayoutDashboard, label: 'Overview' },
  { href: '/dashboard', icon: Activity, label: 'Sensor Dashboard' },
  { href: '/diagnostics', icon: Microscope, label: 'Crop Diagnostics' },
  { href: '/alerts', icon: Bell, label: 'Alerts' },
];

export default function Navbar() {
  const pathname = usePathname();
  return (
    <aside className="w-64 bg-[#0F0F0F] border-r border-white/10 flex flex-col justify-between p-6">
      <div>
        <div className="flex items-center gap-3 mb-10">
          <span className="text-3xl">🌾</span>
          <div className="flex flex-col">
            <span className="font-bold text-lg leading-tight tracking-tight">AgriSense</span>
            <span className="text-xs text-gray-400 font-medium tracking-widest uppercase">AI Assistant</span>
          </div>
        </div>
        <nav className="flex flex-col gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors font-medium text-sm ${pathname === item.href ? 'bg-white/10 text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>
      </div>
      <div className="pt-6 border-t border-white/10">
        <div className="flex items-center gap-2 text-xs font-medium text-gray-500">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          edge-device-sih-01
        </div>
      </div>
    </aside>
  );
}
