import React from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'
import { Footer } from './Footer'

export const Layout: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-[#f4faf9] via-[#f7fbfa] to-[#f0f8f7] text-slate-800 selection:bg-teal-100 selection:text-teal-900">
      <Navbar />
      <main className="flex-1 pb-10">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

export default Layout
