import { Link } from 'react-router-dom';
import logoMark from '../assets/images/litmark-mark-v2.png';

const sizeClasses = {
  compact: {
    mark: 'h-7 w-7',
    text: 'text-lg',
  },
  default: {
    mark: 'h-8 w-8',
    text: 'text-xl',
  },
};

const BrandLogo = ({
  className = '',
  size = 'default',
  tone = 'light',
}) => {
  const classes = sizeClasses[size] || sizeClasses.default;
  const textColor = tone === 'dark'
    ? 'var(--dark-text-primary)'
    : 'var(--text-primary)';

  return (
    <Link
      to="/"
      className={`group inline-flex items-center gap-2.5 ${className}`}
      aria-label="LitMark home"
    >
      <img
        src={logoMark}
        alt=""
        width="32"
        height="32"
        className={`${classes.mark} shrink-0 transition-transform duration-200 group-hover:-translate-y-px`}
      />
      <span
        className={`${classes.text} font-extrabold tracking-tight transition-colors duration-200`}
        style={{ color: textColor }}
      >
        LitMark
      </span>
    </Link>
  );
};

export default BrandLogo;
