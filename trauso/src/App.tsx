import { HomeHero } from "./components/home-hero";
import { Navbar } from "./components/navbar";
import { Footer } from "./components/footer";

function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1">
        <HomeHero />
      </main>
      <Footer />
    </div>
  );
}

export default App;
