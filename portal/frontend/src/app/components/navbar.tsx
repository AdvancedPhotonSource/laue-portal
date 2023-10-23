export default function Navbar() {
    return (
        <div className="navbar bg-base-100">
            <div className="flex-1">
                <a className="btn btn-ghost normal-case text-xl" href="/">Laue Microdiffraction Portal</a>
            </div>
            <div className="flex-none">
                <ul className="menu menu-horizontal px-1">
                    <li><a href="/scans">Scans</a></li>
                    <li><a>Running Reconstructions</a></li>
                    <li><a>Results</a></li>
                </ul>
            </div>
        </div>
    )
}