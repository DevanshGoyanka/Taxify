export const SkeletonRow = ({ cols = 6 }: { cols?: number }) => (
  <tr>
    {Array.from({ length: cols }).map((_, i) => (
      <td key={i}>
        <div style={{
          height: 14, borderRadius: 4,
          background: 'linear-gradient(90deg, #e8edf3 25%, #f4f6f9 50%, #e8edf3 75%)',
          backgroundSize: '400% 100%',
          animation: 'shimmer 1.5s infinite',
          width: `${60 + Math.random() * 30}%`,
        }} />
      </td>
    ))}
  </tr>
);
