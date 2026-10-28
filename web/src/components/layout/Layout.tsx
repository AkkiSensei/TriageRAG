import React from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from './Navbar'
import { Footer } from './Footer'

export const Layout: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-[#F4F6F4] text-[#1A2421] selection:bg-[#E8F5E9] selection:text-[#2D6A4F]">
      <Navbar />
      <main className="flex-1 pb-8">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

