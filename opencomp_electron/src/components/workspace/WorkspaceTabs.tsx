import { useState, useCallback } from 'react';
import './Workspace.css';

export interface TabItem {
  id: string;
  title: string;
  icon?: React.ReactNode;
  content: React.ReactNode;
  closeable?: boolean;
}

interface WorkspaceTabsProps {
  tabs: TabItem[];
  activeTabId?: string;
  onTabChange?: (tabId: string) => void;
  onTabClose?: (tabId: string) => void;
  className?: string;
}

const WorkspaceTabs = ({
  tabs,
  activeTabId,
  onTabChange,
  onTabClose,
  className = '',
}: WorkspaceTabsProps) => {
  const [internalActiveTab, setInternalActiveTab] = useState(tabs[0]?.id || '');

  const activeTab = activeTabId ?? internalActiveTab;

  const handleTabClick = useCallback((tabId: string) => {
    if (onTabChange) {
      onTabChange(tabId);
    } else {
      setInternalActiveTab(tabId);
    }
  }, [onTabChange]);

  const handleTabClose = useCallback((e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    onTabClose?.(tabId);
  }, [onTabClose]);

  const activeTabContent = tabs.find((tab) => tab.id === activeTab)?.content;

  return (
    <div className={`workspace-tabs ${className}`}>
      {/* Tab header container */}
      <div className="workspace-tab-header-container">
        <div className="workspace-tab-header-inner">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`workspace-tab-header ${tab.id === activeTab ? 'is-active' : ''}`}
              onClick={() => handleTabClick(tab.id)}
            >
              {tab.icon && (
                <div className="workspace-tab-header-icon">
                  {tab.icon}
                </div>
              )}
              <div className="workspace-tab-header-title">
                {tab.title}
              </div>
              {tab.closeable && (
                <button
                  className="workspace-tab-header-close"
                  onClick={(e) => handleTabClose(e, tab.id)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="workspace-tab-header-spacer" />
      </div>

      {/* Tab content */}
      <div className="workspace-leaf">
        <div className="workspace-leaf-content">
          {activeTabContent}
        </div>
      </div>
    </div>
  );
};

export default WorkspaceTabs;
