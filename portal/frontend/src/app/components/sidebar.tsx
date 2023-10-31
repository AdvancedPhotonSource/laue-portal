"use client";

import { usePathname } from 'next/navigation';
import Link from 'next/link';


export default function Sidebar() {
  const currentRoute = usePathname();
  const activeStyle = "active";
  const nonActiveStyle = "";
  return (
    <div className="drawer-side">
    <div>
        <div className="navbar bg-base-100 flex-col w-64">
            <div className="flex-1">
                <a className="btn btn-ghost normal-case text-xl" href="/">Laue Portal</a>
            </div>
        </div>
      <label htmlFor="my-drawer-2" aria-label="close sidebar" className="drawer-overlay"></label>
      <ul className="menu text-base-content">
        {/* Sidebar content here */}
        <li>
          <Link href="/scans" className={currentRoute === '/scans' ? activeStyle : nonActiveStyle}>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
            Scans
          </Link>
        </li>
        <li>
          <Link href="/reconstruct" className={currentRoute === '/reconstruct' ? activeStyle : nonActiveStyle}>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            Start Reconstruction
          </Link>
        </li>
        <li>
          <Link href="/runs" className={currentRoute === '/runs' ? activeStyle : nonActiveStyle}>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>
            Run Monitor
          </Link>
        </li>
        <li>
          <Link href="/results" className={currentRoute === '/results' ? activeStyle : nonActiveStyle}>
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18" /><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" /></svg>
            Results
          </Link>
        </li>
      </ul>
    </div>
    </div>
  )
}
