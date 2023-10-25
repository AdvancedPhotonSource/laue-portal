export default function ParamField2({ size, fieldName }) {
  return (
    <div>
      <label className="label">
        <span className="label-text">{fieldName}</span>
      </label>
      <input type="text join-item" className="input input-bordered" />
  </div>
  )
}