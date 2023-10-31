export default function FieldRow({ children }: {children: any}) {
  return (
      <div className="flex flex-row gap-x-4 items-end">
      {children}
    </div>
  )
}