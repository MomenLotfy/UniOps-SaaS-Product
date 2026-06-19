import { useEffect, useRef, useState, ElementType, CSSProperties, ReactNode } from 'react';

interface FadeInProps {
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

export default function FadeIn({ as: Tag = 'div', className = '', style, children }: FadeInProps) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisible(true);
            obs.disconnect();
          }
        });
      },
      { threshold: 0.1 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <Tag ref={ref} className={`lp-fi-in${visible ? ' vis' : ''}${className ? ' ' + className : ''}`} style={style}>
      {children}
    </Tag>
  );
}
