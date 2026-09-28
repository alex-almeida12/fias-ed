import { encode } from "uqr";

type Props = { valor: string; rotulo: string; className?: string };

/** QR code em SVG puro — sem canvas, sem innerHTML, sem data: URL, então nada muda na
 * CSP. `border: 4` é a zona de silêncio que os leitores exigem; `ecc: "M"` aguenta
 * projetor desfocado e reflexo na tela sem inflar o desenho. */
export function QrCode({ valor, rotulo, className = "qr" }: Props) {
  const { data, size } = encode(valor, { border: 4, ecc: "M" });
  const modulos = [];
  for (let y = 0; y < data.length; y++) {
    for (let x = 0; x < data[y].length; x++) {
      if (data[y][x]) modulos.push(<rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} />);
    }
  }
  return (
    <svg className={className} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={rotulo}
      shapeRendering="crispEdges">
      <rect className="qr__fundo" width={size} height={size} />
      <g className="qr__modulos">{modulos}</g>
    </svg>
  );
}
