import { useState, useEffect, useRef, useCallback } from 'react';
import { useGraphStore } from '../store/graphStore';
import './NodeMenu.css';

interface NodeMenuProps {
  position: { x: number; y: number };
  flowPosition: { x: number; y: number };
  onClose: () => void;
}

const NodeMenu = ({ position, flowPosition, onClose }: NodeMenuProps) => {
  const nodeTypes = useGraphStore((state) => state.nodeTypes);
  const addNode = useGraphStore((state) => state.addNode);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Flatten all nodes for search
  const allNodes = Object.entries(nodeTypes).flatMap(([category, nodes]) =>
    nodes.map((node) => ({ ...node, category }))
  );

  // Filter nodes by search
  const filteredNodes = allNodes.filter(
    (node) =>
      node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      node.type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  // Reset selection when search changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [searchQuery]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setSelectedIndex((prev) =>
            prev < filteredNodes.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          event.preventDefault();
          setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0));
          break;
        case 'Enter':
          event.preventDefault();
          if (filteredNodes[selectedIndex]) {
            addNode(filteredNodes[selectedIndex].type, flowPosition.x, flowPosition.y);
            onClose();
          }
          break;
        case 'Escape':
          event.preventDefault();
          onClose();
          break;
        case 'Tab':
          event.preventDefault();
          // Tab cycles through results
          setSelectedIndex((prev) =>
            prev < filteredNodes.length - 1 ? prev + 1 : 0
          );
          break;
      }
    },
    [filteredNodes, selectedIndex, addNode, flowPosition, onClose]
  );

  // Handle node click
  const handleNodeClick = (nodeType: string) => {
    addNode(nodeType, flowPosition.x, flowPosition.y);
    onClose();
  };

  // Group filtered nodes by category
  const groupedNodes = filteredNodes.reduce(
    (acc, node) => {
      if (!acc[node.category]) {
        acc[node.category] = [];
      }
      acc[node.category].push(node);
      return acc;
    },
    {} as Record<string, typeof filteredNodes>
  );

  return (
    <div
      ref={menuRef}
      className="node-menu"
      style={{
        left: position.x,
        top: position.y,
      }}
      onKeyDown={handleKeyDown}
    >
      <div className="node-menu-search">
        <input
          ref={inputRef}
          type="text"
          className="node-menu-input"
          placeholder="Type to search nodes..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          autoFocus
        />
      </div>
      <div className="node-menu-results">
        {Object.entries(groupedNodes).map(([category, nodes]) => (
          <div key={category} className="node-menu-category">
            <div className="node-menu-category-header">{category}</div>
            {nodes.map((node) => {
              const globalIndex = filteredNodes.indexOf(node);
              return (
                <div
                  key={node.type}
                  className={`node-menu-item ${globalIndex === selectedIndex ? 'selected' : ''}`}
                  onClick={() => handleNodeClick(node.type)}
                  onMouseEnter={() => setSelectedIndex(globalIndex)}
                >
                  <span className="node-menu-item-label">{node.label}</span>
                  <span className="node-menu-item-shortcut">{node.type}</span>
                </div>
              );
            })}
          </div>
        ))}
        {filteredNodes.length === 0 && (
          <div className="node-menu-empty">No nodes found</div>
        )}
      </div>
    </div>
  );
};

export default NodeMenu;
