import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Zap, Clock, ArrowRight, Tag } from 'lucide-react';
import { ROUTES } from '@/lib/constants';

const POSTS = [
  { id: 1, title: 'How to reduce cloud costs by 40% with FinOps best practices', excerpt: 'A practical guide to identifying waste, rightsizing resources, and implementing governance without slowing down engineering velocity.', date: '2026-04-10', readTime: '8 min', category: 'FinOps', featured: true },
  { id: 2, title: 'The state of DevSecOps in 2026: Shifting left isn\'t enough', excerpt: 'Security scanning in CI/CD is table stakes now. Here\'s what leading teams are doing differently to actually ship secure software.', date: '2026-04-05', readTime: '6 min', category: 'Security' },
  { id: 3, title: 'Kubernetes operational maturity model: Where does your team stand?', excerpt: 'We surveyed 200+ platform engineers to understand the five stages of K8s operational maturity and what it takes to reach the next level.', date: '2026-03-28', readTime: '12 min', category: 'DevOps' },
  { id: 4, title: 'ML-powered anomaly detection: Beyond simple threshold alerts', excerpt: 'Why static thresholds fail at scale, and how machine learning can surface meaningful signals from your metric streams.', date: '2026-03-20', readTime: '10 min', category: 'ML' },
  { id: 5, title: 'From alert fatigue to alert intelligence: A practical guide', excerpt: 'How to reduce noise by 80% while missing zero critical incidents — the alert strategy that works for on-call teams.', date: '2026-03-14', readTime: '7 min', category: 'Operations' },
  { id: 6, title: 'Multi-cloud cost attribution: Solving the apples-to-oranges problem', excerpt: 'Comparing costs across AWS, GCP, and Azure requires a consistent taxonomy. Here\'s how UniOps normalizes cloud spend data.', date: '2026-03-08', readTime: '9 min', category: 'FinOps' },
];

const CATEGORIES = ['All', 'DevOps', 'Security', 'FinOps', 'ML', 'Operations'];

const CATEGORY_COLORS: Record<string, string> = {
  DevOps: 'text-blue-400 bg-blue-500/10',
  Security: 'text-red-400 bg-red-500/10',
  FinOps: 'text-green-400 bg-green-500/10',
  ML: 'text-purple-400 bg-purple-500/10',
  Operations: 'text-yellow-400 bg-yellow-500/10',
};

export default function Blog() {
  const [activeCategory, setActiveCategory] = [CATEGORIES[0], () => {}];
  const featured = POSTS[0];
  const rest = POSTS.slice(1);

  return (
    <div className="min-h-screen" style={{ background: 'hsl(230 18% 7%)' }}>
      <nav className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'hsl(230 15% 14%)' }}>
        <Link to={ROUTES.HOME} className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'hsl(220 90% 60%)' }}>
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-foreground">UniOps</span>
        </Link>
        <Link to={ROUTES.REGISTER} className="px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: 'hsl(220 90% 60%)' }}>Get started</Link>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-extrabold text-foreground">UniOps Blog</h1>
          <p className="text-muted-foreground mt-2">Insights on DevOps, SecOps, FinOps, and operational excellence</p>
        </motion.div>

        <div className="flex gap-2 flex-wrap">
          {CATEGORIES.map((cat) => (
            <button key={cat}
              className="text-xs px-3 py-1.5 rounded-full font-medium transition-colors"
              style={{ background: cat === CATEGORIES[0] ? 'hsl(220 90% 60%)' : 'hsl(230 15% 12%)', color: cat === CATEGORIES[0] ? 'white' : 'hsl(215 16% 57%)', border: '1px solid hsl(230 15% 16%)' }}>
              {cat}
            </button>
          ))}
        </div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden p-8 rounded-2xl border cursor-pointer hover:border-blue-500/30 transition-all group"
          style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full text-green-400 bg-green-500/10">Featured</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[featured.category]}`}>{featured.category}</span>
          </div>
          <h2 className="text-xl font-bold text-foreground group-hover:text-blue-400 transition-colors mb-2">{featured.title}</h2>
          <p className="text-sm text-muted-foreground mb-4">{featured.excerpt}</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>{featured.date}</span>
              <span>·</span>
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{featured.readTime}</span>
            </div>
            <span className="flex items-center gap-1 text-xs text-blue-400">Read article <ArrowRight className="w-3 h-3" /></span>
          </div>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-4">
          {rest.map((post, i) => (
            <motion.div key={post.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
              className="p-5 rounded-2xl border cursor-pointer hover:border-blue-500/30 transition-all group"
              style={{ background: 'hsl(230 18% 8%)', borderColor: 'hsl(230 15% 14%)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Tag className="w-3 h-3 text-muted-foreground" />
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CATEGORY_COLORS[post.category] ?? ''}`}>{post.category}</span>
              </div>
              <h3 className="text-sm font-bold text-foreground group-hover:text-blue-400 transition-colors mb-1.5 line-clamp-2">{post.title}</h3>
              <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{post.excerpt}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>{post.date}</span><span>·</span>
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{post.readTime}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
}
