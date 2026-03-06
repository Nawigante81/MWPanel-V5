"""
Task Management Service - System Zadań dla Agentów

Zarządzanie zadaniami, przypomnieniami i follow-upami dla agentów nieruchomości.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Status zadania"""
    PENDING = "pending"              # Oczekujące
    IN_PROGRESS = "in_progress"      # W trakcie
    COMPLETED = "completed"          # Ukończone
    CANCELLED = "cancelled"          # Anulowane


class TaskPriority(str, Enum):
    """Priorytet zadania"""
    LOW = "low"                      # Niski
    MEDIUM = "medium"                # Średni
    HIGH = "high"                    # Wysoki
    URGENT = "urgent"                # Pilny


class RelatedType(str, Enum):
    """Typ powiązanego obiektu"""
    LISTING = "listing"              # Oferta
    CLIENT = "client"                # Klient
    VIEWING = "viewing"              # Prezentacja
    COMMISSION = "commission"        # Prowizja
    GENERAL = "general"              # Ogólne


@dataclass
class Task:
    """Zadanie dla agenta"""
    id: str
    title: str
    description: Optional[str]
    
    # Przypisanie
    assigned_to: str                 # ID agenta
    created_by: str                  # ID twórcy
    
    # Status
    status: TaskStatus
    priority: TaskPriority
    
    # Daty
    created_at: datetime
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    
    # Powiązanie
    related_type: Optional[RelatedType]
    related_id: Optional[str]
    
    # Dodatkowe
    notes: Optional[str]
    reminder_sent: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'created_by': self.created_by,
            'status': self.status.value,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'related_type': self.related_type.value if self.related_type else None,
            'related_id': self.related_id,
            'notes': self.notes,
            'reminder_sent': self.reminder_sent,
            'is_overdue': self.is_overdue(),
        }
    
    def is_overdue(self) -> bool:
        """Sprawdź czy zadanie jest przeterminowane"""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            return False
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date
    
    def days_until_due(self) -> Optional[int]:
        """Ile dni pozostało do terminu"""
        if not self.due_date:
            return None
        delta = self.due_date - datetime.utcnow()
        return delta.days


@dataclass
class TaskTemplate:
    """Szablon zadania"""
    id: str
    name: str
    title_template: str
    description_template: str
    default_priority: TaskPriority
    default_due_days: int
    related_type: Optional[RelatedType]
    
    def generate_task(
        self,
        assigned_to: str,
        created_by: str,
        variables: Dict[str, str],
        related_id: Optional[str] = None
    ) -> Task:
        """Wygeneruj zadanie z szablonu"""
        title = self.title_template.format(**variables)
        description = self.description_template.format(**variables)
        
        return Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            assigned_to=assigned_to,
            created_by=created_by,
            status=TaskStatus.PENDING,
            priority=self.default_priority,
            created_at=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=self.default_due_days),
            completed_at=None,
            related_type=self.related_type,
            related_id=related_id,
            notes=None,
            reminder_sent=False,
        )


# Predefiniowane szablony
TASK_TEMPLATES = {
    "follow_up_client": TaskTemplate(
        id="follow_up_client",
        name="Follow-up z klientem",
        title_template="Follow-up: {client_name}",
        description_template="Skontaktuj się z klientem {client_name} w sprawie {subject}",
        default_priority=TaskPriority.MEDIUM,
        default_due_days=2,
        related_type=RelatedType.CLIENT,
    ),
    "viewing_follow_up": TaskTemplate(
        id="viewing_follow_up",
        name="Follow-up po prezentacji",
        title_template="Follow-up po prezentacji: {address}",
        description_template="Skontaktuj się z klientem po prezentacji nieruchomości {address}",
        default_priority=TaskPriority.HIGH,
        default_due_days=1,
        related_type=RelatedType.VIEWING,
    ),
    "contract_deadline": TaskTemplate(
        id="contract_deadline",
        name="Termin umowy",
        title_template="Termin umowy: {address}",
        description_template="Zbliża się termin podpisania umowy dla {address}",
        default_priority=TaskPriority.URGENT,
        default_due_days=0,
        related_type=RelatedType.LISTING,
    ),
    "price_update": TaskTemplate(
        id="price_update",
        name="Aktualizacja ceny",
        title_template="Rozważ aktualizację ceny: {address}",
        description_template="Oferta {address} jest na rynku od {days_on_market} dni. Rozważ obniżkę ceny.",
        default_priority=TaskPriority.MEDIUM,
        default_due_days=3,
        related_type=RelatedType.LISTING,
    ),
    "commission_invoice": TaskTemplate(
        id="commission_invoice",
        name="Faktura prowizyjna",
        title_template="Wystaw fakturę prowizyjną: {deal_address}",
        description_template="Transakcja dla {deal_address} zakończona. Wystaw fakturę prowizyjną.",
        default_priority=TaskPriority.HIGH,
        default_due_days=2,
        related_type=RelatedType.COMMISSION,
    ),
}


class TaskManagementService:
    """
    Serwis zarządzania zadaniami dla agentów.
    
    Umożliwia tworzenie, przypisywanie i śledzenie zadań
    związanych z ofertami, klientami i transakcjami.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def create_task(
        self,
        title: str,
        assigned_to: str,
        description: Optional[str] = None,
        created_by: str = "system",
        due_date: Optional[datetime] = None,
        priority: str = "medium",
        related_type: Optional[str] = None,
        related_id: Optional[str] = None,
    ) -> Task:
        """
        Utwórz nowe zadanie.
        
        Args:
            title: Tytuł zadania
            assigned_to: ID agenta
            description: Opis zadania
            created_by: ID twórcy
            due_date: Termin wykonania
            priority: Priorytet (low/medium/high/urgent)
            related_type: Typ powiązanego obiektu
            related_id: ID powiązanego obiektu
        """
        try:
            task_priority = TaskPriority(priority)
        except ValueError:
            task_priority = TaskPriority.MEDIUM
        
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            assigned_to=assigned_to,
            created_by=created_by,
            status=TaskStatus.PENDING,
            priority=task_priority,
            created_at=datetime.utcnow(),
            due_date=due_date,
            completed_at=None,
            related_type=RelatedType(related_type) if related_type else None,
            related_id=related_id,
            notes=None,
            reminder_sent=False,
        )
        
        # Zapisz w bazie
        self._save_task(task)
        
        logger.info(f"Task created: {title} for user {assigned_to}")
        
        return task
    
    async def create_from_template(
        self,
        template_id: str,
        assigned_to: str,
        created_by: str,
        variables: Dict[str, str],
        related_id: Optional[str] = None,
    ) -> Optional[Task]:
        """Utwórz zadanie z szablonu"""
        template = TASK_TEMPLATES.get(template_id)
        if not template:
            logger.warning(f"Template not found: {template_id}")
            return None
        
        task = template.generate_task(
            assigned_to=assigned_to,
            created_by=created_by,
            variables=variables,
            related_id=related_id
        )
        
        self._save_task(task)
        
        logger.info(f"Task created from template {template_id}: {task.title}")
        
        return task
    
    async def get_task(self, task_id: uuid.UUID) -> Optional[Task]:
        """Pobierz zadanie po ID"""
        # W rzeczywistej implementacji: zapytanie do bazy
        # Tutaj symulacja - w prawdziwej app byłoby to query
        return self._get_task_from_db(task_id)
    
    async def list_tasks(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        related_to: Optional[str] = None,
        include_completed: bool = False,
    ) -> List[Task]:
        """
        Lista zadań z filtrowaniem.
        
        Args:
            user_id: Filtruj po przypisanym agencie
            status: Filtruj po statusie
            priority: Filtruj po priorytecie
            related_to: Filtruj po powiązanym obiekcie (format: "type:id")
            include_completed: Czy uwzględnić ukończone
        """
        # W rzeczywistej implementacji: zapytanie do bazy
        tasks = self._get_tasks_from_db(
            user_id=user_id,
            status=status,
            priority=priority,
            related_to=related_to,
            include_completed=include_completed
        )
        
        # Sortuj: pilne i przeterminowane na górze
        tasks.sort(key=lambda t: (
            t.status != TaskStatus.PENDING,
            t.priority != TaskPriority.URGENT,
            t.priority != TaskPriority.HIGH,
            t.due_date or datetime.max
        ))
        
        return tasks
    
    async def update_task(
        self,
        task_id: uuid.UUID,
        **kwargs
    ) -> Optional[Task]:
        """Zaktualizuj zadanie"""
        task = await self.get_task(task_id)
        if not task:
            return None
        
        # Aktualizuj pola
        if 'title' in kwargs:
            task.title = kwargs['title']
        if 'description' in kwargs:
            task.description = kwargs['description']
        if 'status' in kwargs:
            task.status = TaskStatus(kwargs['status'])
        if 'priority' in kwargs:
            task.priority = TaskPriority(kwargs['priority'])
        if 'due_date' in kwargs:
            task.due_date = kwargs['due_date']
        if 'notes' in kwargs:
            task.notes = kwargs['notes']
        
        self._update_task_in_db(task)
        
        logger.info(f"Task updated: {task_id}")
        
        return task
    
    async def complete_task(
        self,
        task_id: uuid.UUID,
        notes: Optional[str] = None,
        completed_by: Optional[str] = None,
    ) -> Optional[Task]:
        """Oznacz zadanie jako ukończone"""
        task = await self.get_task(task_id)
        if not task:
            return None
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        
        if notes:
            task.notes = notes
        
        self._update_task_in_db(task)
        
        logger.info(f"Task completed: {task_id} by {completed_by or 'unknown'}")
        
        return task
    
    async def delete_task(self, task_id: uuid.UUID) -> bool:
        """Usuń zadanie"""
        # W rzeczywistej implementacji: usunięcie z bazy
        logger.info(f"Task deleted: {task_id}")
        return True
    
    async def get_user_dashboard(self, user_id: str) -> Dict[str, Any]:
        """
        Pobierz dashboard zadań dla użytkownika.
        
        Returns:
            Statystyki zadań: pending, overdue, due_today, completed_today
        """
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        all_tasks = await self.list_tasks(user_id=user_id, include_completed=True)
        
        pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]
        in_progress = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
        overdue = [t for t in all_tasks if t.is_overdue()]
        
        due_today = [
            t for t in all_tasks
            if t.due_date and today <= t.due_date < tomorrow
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]
        
        completed_today = [
            t for t in all_tasks
            if t.completed_at and today <= t.completed_at < tomorrow
        ]
        
        # Zadania z wysokim priorytetem
        urgent = [t for t in pending if t.priority == TaskPriority.URGENT]
        high_priority = [t for t in pending if t.priority == TaskPriority.HIGH]
        
        return {
            'user_id': user_id,
            'summary': {
                'total_pending': len(pending),
                'in_progress': len(in_progress),
                'overdue': len(overdue),
                'due_today': len(due_today),
                'completed_today': len(completed_today),
                'urgent': len(urgent),
                'high_priority': len(high_priority),
            },
            'overdue_tasks': [t.to_dict() for t in overdue[:5]],
            'due_today_tasks': [t.to_dict() for t in due_today[:5]],
            'urgent_tasks': [t.to_dict() for t in urgent[:5]],
        }
    
    async def get_upcoming_tasks(
        self,
        user_id: str,
        days: int = 7,
    ) -> List[Task]:
        """Pobierz nadchodzące zadania na następne N dni"""
        end_date = datetime.utcnow() + timedelta(days=days)
        
        all_tasks = await self.list_tasks(user_id=user_id)
        
        upcoming = [
            t for t in all_tasks
            if t.due_date and t.due_date <= end_date
            and t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
        ]
        
        # Sortuj po dacie
        upcoming.sort(key=lambda t: t.due_date or datetime.max)
        
        return upcoming
    
    async def send_reminders(self) -> List[Task]:
        """
        Wyślij przypomnienia o zadaniach.
        
        Returns:
            Lista zadań, dla których wysłano przypomnienia.
        """
        reminder_tasks = []
        
        # Znajdź zadania z przypomnieniem na dziś
        tasks = await self.list_tasks(include_completed=False)
        
        for task in tasks:
            if task.reminder_sent:
                continue
            
            if not task.due_date:
                continue
            
            # Przypomnienie dzień przed terminem
            reminder_date = task.due_date - timedelta(days=1)
            
            if datetime.utcnow() >= reminder_date:
                # Wyślij przypomnienie (w rzeczywistej app - powiadomienie)
                task.reminder_sent = True
                self._update_task_in_db(task)
                
                reminder_tasks.append(task)
                
                logger.info(f"Reminder sent for task: {task.id}")
        
        return reminder_tasks
    
    async def create_auto_tasks_for_listing(self, listing_id: str, agent_id: str):
        """Automatycznie utwórz zadania dla nowej oferty"""
        tasks = []
        
        # Zadanie: aktualizacja zdjęć
        task = await self.create_task(
            title="Dodaj profesjonalne zdjęcia",
            assigned_to=agent_id,
            description="Zorganizuj sesję zdjęciową dla nowej oferty",
            related_type="listing",
            related_id=listing_id,
            priority="high",
            due_date=datetime.utcnow() + timedelta(days=3),
        )
        tasks.append(task)
        
        # Zadanie: weryfikacja dokumentów
        task = await self.create_task(
            title="Zweryfikuj dokumenty właściciela",
            assigned_to=agent_id,
            description="Sprawdź akt własności i inne wymagane dokumenty",
            related_type="listing",
            related_id=listing_id,
            priority="urgent",
            due_date=datetime.utcnow() + timedelta(days=1),
        )
        tasks.append(task)
        
        return tasks
    
    async def create_follow_up_task(
        self,
        client_id: str,
        client_name: str,
        agent_id: str,
        subject: str,
        due_days: int = 2,
    ) -> Task:
        """Utwórz zadanie follow-up z klientem"""
        return await self.create_from_template(
            template_id="follow_up_client",
            assigned_to=agent_id,
            created_by="system",
            variables={
                'client_name': client_name,
                'subject': subject,
            },
            related_id=client_id,
        )
    
    # ==========================================================================
    # Metody pomocnicze (symulacja bazy danych)
    # ==========================================================================
    
    def _save_task(self, task: Task):
        """Zapisz zadanie w bazie"""
        # W rzeczywistej implementacji: session.add(task_model); session.commit()
        pass
    
    def _get_task_from_db(self, task_id: uuid.UUID) -> Optional[Task]:
        """Pobierz zadanie z bazy"""
        # W rzeczywistej implementacji: query do bazy
        return None
    
    def _get_tasks_from_db(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        related_to: Optional[str] = None,
        include_completed: bool = False,
    ) -> List[Task]:
        """Pobierz listę zadań z bazy"""
        # W rzeczywistej implementacji: query do bazy z filtrami
        return []
    
    def _update_task_in_db(self, task: Task):
        """Zaktualizuj zadanie w bazie"""
        # W rzeczywistej implementacji: session.merge(task_model); session.commit()
        pass
