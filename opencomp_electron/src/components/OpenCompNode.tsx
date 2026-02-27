import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { OpenCompNodeData } from '../store/graphStore';
import './OpenCompNode.css';

// Socket color mapping
const SOCKET_COLORS: Record<string, string> = {
  'OC_NS_image': 'var(--socket-image)',
  'OC_NS_float': 'var(--socket-float)',
  'OC_NS_int': 'var(--socket-int)',
  'OC_NS_bool': 'var(--socket-bool)',
  'OC_NS_vector': 'var(--socket-vector)',
};

type OpenCompNodeProps = NodeProps & {
  data: OpenCompNodeData;
};

const OpenCompNode = ({ data, selected }: OpenCompNodeProps) => {
  const { label, nodeType, inputs, outputs } = data;

  // Get node category color
  const getCategoryColor = () => {
    if (nodeType.includes('viewer')) return 'var(--brand-primary)';
    if (nodeType.includes('read') || nodeType.includes('write')) return 'var(--socket-image)';
    if (nodeType.includes('grade') || nodeType.includes('cdl') || nodeType.includes('constant')) return 'var(--status-info)';
    if (nodeType.includes('blur') || nodeType.includes('sharpen')) return 'var(--socket-float)';
    if (nodeType.includes('over') || nodeType.includes('merge') || nodeType.includes('shuffle')) return 'var(--socket-vector)';
    if (nodeType.includes('transform') || nodeType.includes('crop')) return 'var(--status-warning)';
    if (nodeType.includes('roto')) return 'var(--socket-bool)';
    return 'var(--text-muted)';
  };

  return (
    <div className={`oc-node ${selected ? 'oc-node-selected' : ''}`}>
      {/* Input handles on TOP - Nuke style */}
      {inputs.map((input: { name: string; type: string }, index: number) => (
        <Handle
          key={`in-${input.name}`}
          type="target"
          position={Position.Top}
          id={input.name}
          style={{
            backgroundColor: SOCKET_COLORS[input.type] || 'var(--text-muted)',
            left: inputs.length === 1 ? '50%' : `${((index + 1) / (inputs.length + 1)) * 100}%`,
          }}
          title={input.name}
        />
      ))}

      {/* Header */}
      <div
        className="oc-node-header"
        style={{ backgroundColor: getCategoryColor() }}
      >
        <span className="oc-node-label">{label}</span>
      </div>

      {/* Output handles on BOTTOM - Nuke style */}
      {outputs.map((output: { name: string; type: string }, index: number) => (
        <Handle
          key={`out-${output.name}`}
          type="source"
          position={Position.Bottom}
          id={output.name}
          style={{
            backgroundColor: SOCKET_COLORS[output.type] || 'var(--text-muted)',
            left: outputs.length === 1 ? '50%' : `${((index + 1) / (outputs.length + 1)) * 100}%`,
          }}
          title={output.name}
        />
      ))}
    </div>
  );
};

export default memo(OpenCompNode);
