export default function CollapseCard({ title, children }) {
    return (
        <div className="collapse shadow-xl bg-base-100 collapse-plus">
            <input type="checkbox" />
            <div className="collapse-title text-xl font-medium bg-100 ">
                {title}
            </div>
            <div className="collapse-content">
                {children}
            </div>
        </div >
    )
}