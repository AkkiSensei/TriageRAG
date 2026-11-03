import React from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'
import { Footer } from './Footer'

export const Layout: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-100 selection:bg-teal-100 dark:selection:bg-teal-900/60 selection:text-teal-900 dark:selection:text-teal-200 transition-colors duration-150">
      <Navbar />
      <main className="flex-1 pb-10">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

export default Layout
