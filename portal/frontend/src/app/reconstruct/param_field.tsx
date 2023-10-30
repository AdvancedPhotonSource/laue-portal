export default function ParamField({size, fieldName}) {
  let width;

  // Workaround for tailwind. Needs to see whole custom names
  if (size === 'lg') {
    width = 'w-[250px]'
  } else if (size === 'md') {
    width = 'w-[150px]'
  } else if (size === 'sm') {
    width = 'w-[117px]'
  }

  return (
    <div className={width}>
      <label className="label">
        <span className="label-text">{fieldName}</span>
      </label>
      <input type="text join-item" className={`input input-bordered w-full`} />
  </div>
  )
}