export default function Reconstruct() {
    return (
        <div className="space-y-4">
            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Calibration
                </div>
                <div className="collapse-content">
                    <p>hello</p>
                </div>
            </div>
            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Mask
                </div>
                <div className="collapse-content">
                    <p>hello</p>
                </div>
            </div>
            <div className="collapse shadow-xl bg-base-100 collapse-plus">
                <input type="checkbox" />
                <div className="collapse-title text-xl font-medium bg-100 ">
                    Detector
                </div>
                <div className="collapse-content">
                    <p>hello</p>
                </div>
            </div>
        </div>
    )
}