import { useState } from 'react';
import { useGraphStore } from '../store/graphStore';
import './NodeLibrary.css';

const NodeLibrary = () => {
  const nodeTypes = useGraphStore((state) => state.nodeTypes);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(['Input/Output', 'Color', 'Merge'])
  );
  const [searchQuery, setSearchQuery] = useState('');

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/opencomp-node-type', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  // Filter nodes by search query
  const filteredCategories = Object.entries(nodeTypes).reduce(
    (acc, [category, nodes]) => {
      const filteredNodes = nodes.filter((node) =>
        node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        node.type.toLowerCase().includes(searchQuery.toLowerCase())
      );
      if (filteredNodes.length > 0) {
        acc[category] = filteredNodes;
      }
      return acc;
    },
    {} as typeof nodeTypes
  );

  return (
    <div className="node-library">
      <div className="panel-header">Node Library</div>
      <div className="node-library-search">
        <input
          type="text"
          className="input"
          placeholder="Search nodes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ width: '100%' }}
        />
      </div>
      <div className="node-library-content">
        {Object.entries(filteredCategories).map(([category, nodes]) => (
          <div key={category} className="node-library-category">
            <button
              className="node-library-category-header"
              onClick={() => toggleCategory(category)}
            >
              <span className="node-library-category-icon">
                {expandedCategories.has(category) ? '▼' : '▶'}
              </span>
              <span className="node-library-category-name">{category}</span>
              <span className="node-library-category-count">{nodes.length}</span>
            </button>
            {expandedCategories.has(category) && (
              <div className="node-library-category-items">
                {nodes.map((node) => (
                  <div
                    key={node.type}
                    className="node-library-item"
                    draggable
                    onDragStart={(e) => onDragStart(e, node.type)}
                  >
                    <span className="node-library-item-label">{node.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {Object.keys(filteredCategories).length === 0 && (
          <div className="node-library-empty">
            {searchQuery ? 'No nodes match your search' : 'Loading nodes...'}
          </div>
        )}
      </div>
    </div>
  );
};

export default NodeLibrary;
