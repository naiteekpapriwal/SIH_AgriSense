'use client';
import { useEffect, useState, useRef } from 'react';
import { Thermometer, Droplets, Sprout, Bell } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: number | string;
  unit?: string;
  icon: 'thermometer' | 'droplets' | 'sprout' | 'bell';
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
}

export default function StatCard({
  label,
  value,
  unit,
  icon,
  trend,
  trendValue,
}: StatCardProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const animatedRef = useRef(false);

  useEffect(() => {
    if (animatedRef.current) {
      setDisplayValue(typeof value === 'number' ? value : 0);
      return;
    }
    if (typeof value !== 'number') {
      animatedRef.current = true;
      return;
    }
    animatedRef.current = true;
    const target = value;
    const duration = 800;
    const steps = 30;
    const increment = target / steps;
    let current = 0;
    let step = 0;
    const timer = setInterval(() => {
      step++;
      current = Math.min(current + increment, target);
      setDisplayValue(Math.round(current * 10) / 10);
      if (step >= steps) {
        setDisplayValue(target);
        clearInterval(timer);
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);

  const renderIcon = () => {
    switch (icon) {
      case 'thermometer': return <Thermometer className="text-orange-500" size={24} />;
      case 'droplets': return <Droplets className="text-blue-500" size={24} />;
      case 'sprout': return <Sprout className="text-green-500" size={24} />;
      case 'bell': return <Bell className="text-red-500" size={24} />;
      default: return null;
    }
  };

  const renderTrendBadge = () => {
    if (!trend || !trendValue) return null;
    let bg, text, border;
    if (trend === 'stable' || trendValue === 'Normal' || trendValue === 'OK' || trendValue === 'None') {
      bg = 'bg-gray-500/10';
      text = 'text-gray-400';
      border = 'border-gray-500/20';
    } else if (trend === 'up' && icon === 'bell') {
      bg = 'bg-red-500/10';
      text = 'text-red-400';
      border = 'border-red-500/20';
    } else if (trend === 'up' && icon === 'thermometer') {
      bg = 'bg-orange-500/10';
      text = 'text-orange-400';
      border = 'border-orange-500/20';
    } else if (trend === 'down' && icon === 'sprout') {
      bg = 'bg-yellow-500/10';
      text = 'text-yellow-400';
      border = 'border-yellow-500/20';
    } else {
      bg = 'bg-blue-500/10';
      text = 'text-blue-400';
      border = 'border-blue-500/20';
    }
    
    return (
      <span className={`text-xs font-semibold px-2 py-1 rounded-full border ${bg} ${text} ${border}`}>
        {trendValue}
      </span>
    );
  };

  return (
    <div className="bg-[#1A1A1A] border border-white/10 rounded-xl p-6 shadow-xl flex flex-col gap-4 transition-all hover:bg-[#222]">
      <div className="flex items-center justify-between">
        <div className="p-2 bg-white/5 rounded-lg border border-white/5">
          {renderIcon()}
        </div>
        {renderTrendBadge()}
      </div>
      
      <div>
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-white">
            {typeof value === 'number' ? displayValue.toFixed(1) : value}
          </span>
          {unit && <span className="text-lg font-medium text-gray-400">{unit}</span>}
        </div>
        <div className="text-xs font-semibold text-gray-400 tracking-wider uppercase mt-1">
          {label}
        </div>
      </div>
    </div>
  );
}
